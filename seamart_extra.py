import shutil
import tkinter as tk
from datetime import datetime, date
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import sys

def install(SeaMart):
    # Resolve shared helpers from the main application module. Without this,
    # callbacks in this extension would raise NameError when opening the tab.
    app_module = sys.modules[SeaMart.__module__]
    globals()['db'] = app_module.db
    globals()['money'] = app_module.money
    original_init = SeaMart.__init__
    def extended_init(self):
        original_init(self)
        self.held_carts = []
        self.extra_tab = tk.Frame(self.tabs, bg="#eef3f8")
        self.tabs.add(self.extra_tab, text="Transaksi & Backup")
        bar = tk.Frame(self.extra_tab, bg="#eef3f8"); bar.pack(fill="x", padx=10, pady=10)
        ttk.Button(bar, text="Muat Transaksi", command=self.extra_refresh_sales).pack(side="left", padx=4)
        ttk.Button(bar, text="Batalkan Transaksi", command=self.extra_cancel_sale).pack(side="left", padx=4)
        ttk.Button(bar, text="Tahan Keranjang", command=self.extra_hold).pack(side="left", padx=4)
        ttk.Button(bar, text="Lanjutkan Keranjang", command=self.extra_resume).pack(side="left", padx=4)
        ttk.Button(bar, text="Backup Database", command=self.extra_backup).pack(side="left", padx=4)
        ttk.Button(bar, text="Pulihkan Backup", command=self.extra_restore).pack(side="left", padx=4)
        self.extra_sales_tree = self.tree(self.extra_tab,
            ("invoice","created","payment","total","status"),
            ("Invoice","Tanggal","Metode","Total","Status"), 150)
        self.extra_refresh_sales()
    SeaMart.__init__ = extended_init

    def refresh_sales(self):
        self.extra_sales_tree.delete(*self.extra_sales_tree.get_children())
        with db() as c:
            rows=c.execute("SELECT invoice,created,payment,total,status FROM sales ORDER BY id DESC LIMIT 1000")
            for r in rows:
                self.extra_sales_tree.insert("","end",iid=str(r["invoice"]),
                    values=(r["invoice"],r["created"],r["payment"],money(r["total"]),r["status"]))
    def cancel_sale(self):
        selected=self.extra_sales_tree.selection()
        if not selected:
            messagebox.showinfo("SeaMart","Pilih transaksi yang akan dibatalkan."); return
        invoice=selected[0]
        if not messagebox.askyesno("Konfirmasi Pembatalan",
            "Batalkan transaksi "+invoice+"? Stok akan dikembalikan satu kali."):
            return
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db() as c:
            sale=c.execute("SELECT id,total,status FROM sales WHERE invoice=?",(invoice,)).fetchone()
            if not sale or sale["status"]!="LUNAS":
                messagebox.showwarning("SeaMart","Transaksi tidak ditemukan atau sudah dibatalkan."); return
            items=c.execute("SELECT product_id,name,qty FROM sale_items WHERE sale_id=?",(sale["id"],)).fetchall()
            for item in items:
                if item["product_id"] is not None:
                    p=c.execute("SELECT non_stock FROM products WHERE id=?",(item["product_id"],)).fetchone()
                    if p and not p["non_stock"]:
                        c.execute("UPDATE products SET stock=stock+? WHERE id=?",(item["qty"],item["product_id"]))
                        c.execute("INSERT INTO movements(created,product_id,kind,qty,note) VALUES(?,?,?,?,?)",
                            (now,item["product_id"],"PEMBATALAN",item["qty"],invoice))
            c.execute("UPDATE sales SET status='DIBATALKAN' WHERE id=?",(sale["id"],))
            c.execute("INSERT INTO cashbook(created,kind,description,amount) VALUES(?,?,?,?)",
                (now,"KELUAR","Pembatalan penjualan "+invoice,sale["total"]))
        self.refresh_all(); self.extra_refresh_sales()
        messagebox.showinfo("SeaMart","Transaksi dibatalkan dan stok barang dikembalikan.")
    def hold(self):
        if not self.cart:
            messagebox.showinfo("SeaMart","Keranjang masih kosong."); return
        self.held_carts.append([dict(x) for x in self.cart])
        self.cart=[]; self.draw_cart()
        messagebox.showinfo("SeaMart","Keranjang disimpan sementara pada sesi aplikasi ini.")
    def resume(self):
        if not self.held_carts:
            messagebox.showinfo("SeaMart","Tidak ada transaksi yang ditahan."); return
        if self.cart and not messagebox.askyesno("SeaMart","Keranjang aktif akan ditahan. Lanjutkan transaksi sebelumnya?"):
            return
        if self.cart:self.held_carts.append([dict(x) for x in self.cart])
        self.cart=self.held_carts.pop(0); self.draw_cart()
    def backup(self):
        target=filedialog.asksaveasfilename(defaultextension=".db",
            filetypes=[("Database SeaMart","*.db")], initialfile="SeaMart_Backup.db")
        if not target:return
        try:
            with db() as c:
                dest=sqlite3.connect(target)
                c.backup(dest); dest.close()
            messagebox.showinfo("Backup","Backup database berhasil disimpan.")
        except Exception as e:messagebox.showerror("Backup gagal",str(e))
    def restore(self):
        source=filedialog.askopenfilename(filetypes=[("Database SeaMart","*.db"),("Semua file","*.*")])
        if not source:return
        if not messagebox.askyesno("Pulihkan Backup",
            "Data SeaMart saat ini akan diganti dengan isi backup. Lanjutkan?"):
            return
        try:
            check=sqlite3.connect(source)
            ok=check.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            check.close()
            if not ok:raise ValueError("File backup tidak valid.")
            with db() as c:
                src=sqlite3.connect(source)
                src.backup(c.connection if hasattr(c,"connection") else c)
                src.close()
            self.refresh_all(); self.extra_refresh_sales()
            messagebox.showinfo("Pulihkan Backup","Database berhasil dipulihkan.")
        except Exception as e:messagebox.showerror("Pulihkan gagal",str(e))
    SeaMart.extra_refresh_sales=refresh_sales
    SeaMart.extra_cancel_sale=cancel_sale
    SeaMart.extra_hold=hold
    SeaMart.extra_resume=resume
    SeaMart.extra_backup=backup
    SeaMart.extra_restore=restore
