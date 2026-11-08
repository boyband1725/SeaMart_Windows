import os, sqlite3, csv, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

ROOT=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"SeaMartPOS"
ROOT.mkdir(parents=True,exist_ok=True)
DB=ROOT/"seamart.db"

def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, code TEXT UNIQUE, barcode TEXT UNIQUE, name TEXT NOT NULL, category TEXT DEFAULT 'Umum', cost REAL DEFAULT 0, price REAL DEFAULT 0, stock REAL DEFAULT 0, min_stock REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, invoice TEXT UNIQUE, created TEXT, payment TEXT, subtotal REAL, discount REAL, total REAL, received REAL, change_due REAL);
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, name TEXT, qty REAL, price REAL, cost REAL, line_total REAL);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, created TEXT, product_id INTEGER, kind TEXT, qty REAL, note TEXT);
        """)
        c.execute("INSERT OR IGNORE INTO products(code,name,category,price,stock) VALUES('DEMO-001','Contoh Barang','Umum',10000,10)")

class SeaMart(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("SeaMart POS V15"); self.geometry("1100x700"); self.minsize(900,600); self.cart=[]
        self.configure(bg="#f3f6fa"); self.style=ttk.Style(self); self.style.theme_use("clam")
        self.style.configure("Treeview",rowheight=30,font=("Segoe UI",10)); self.style.configure("Treeview.Heading",font=("Segoe UI",10,"bold"))
        head=tk.Frame(self,bg="#123c69",height=65); head.pack(fill="x"); tk.Label(head,text="SeaMart POS",fg="white",bg="#123c69",font=("Segoe UI",20,"bold")).pack(side="left",padx=20,pady=12)
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=12,pady=12)
        self.cash=tk.Frame(self.tabs,bg="#f3f6fa"); self.mastertab=tk.Frame(self.tabs,bg="#f3f6fa"); self.report=tk.Frame(self.tabs,bg="#f3f6fa")
        self.tabs.add(self.cash,text="Kasir"); self.tabs.add(self.mastertab,text="Master Barang"); self.tabs.add(self.report,text="Riwayat")
        self.build_cash(); self.build_master(); self.build_report(); self.refresh()
    def tree(self,parent,cols,heads):
        t=ttk.Treeview(parent,columns=cols,show="headings")
        for col,h in zip(cols,heads): t.heading(col,text=h); t.column(col,width=130,anchor="w")
        return t
    def build_cash(self):
        bar=tk.Frame(self.cash,bg="#f3f6fa"); bar.pack(fill="x",padx=10,pady=10)
        self.search=tk.StringVar(); e=ttk.Entry(bar,textvariable=self.search,width=38); e.pack(side="left"); e.bind("<Return>",lambda _:self.add_cart())
        ttk.Button(bar,text="Tambah ke keranjang",command=self.add_cart).pack(side="left",padx=8)
        self.carttree=self.tree(self.cash,("name","qty","price","total"),("Barang","Qty","Harga","Jumlah")); self.carttree.pack(fill="both",expand=True,padx=10,pady=8)
        foot=tk.Frame(self.cash,bg="#f3f6fa"); foot.pack(fill="x",padx=10,pady=10)
        self.totalvar=tk.StringVar(value="Total: Rp0"); tk.Label(foot,textvariable=self.totalvar,bg="#f3f6fa",font=("Segoe UI",18,"bold")).pack(side="left")
        ttk.Button(foot,text="Hapus keranjang",command=self.clear).pack(side="right",padx=5); ttk.Button(foot,text="Bayar Tunai",command=lambda:self.pay("Tunai")).pack(side="right",padx=5); ttk.Button(foot,text="Bayar QRIS",command=lambda:self.pay("QRIS")).pack(side="right",padx=5)
    def build_master(self):
        bar=tk.Frame(self.mastertab,bg="#f3f6fa"); bar.pack(fill="x",padx=10,pady=10)
        ttk.Button(bar,text="Impor CSV",command=self.import_csv).pack(side="left"); ttk.Button(bar,text="Tambah Barang",command=self.add_product).pack(side="left",padx=8); ttk.Button(bar,text="Ekspor CSV",command=self.export_csv).pack(side="left")
        self.ptree=self.tree(self.mastertab,("code","barcode","name","category","price","stock"),("Kode","Barcode","Nama Barang","Kategori","Harga Jual","Stok")); self.ptree.pack(fill="both",expand=True,padx=10,pady=10)
    def build_report(self):
        bar=tk.Frame(self.report,bg="#f3f6fa"); bar.pack(fill="x",padx=10,pady=10); ttk.Button(bar,text="Muat Ulang",command=self.refresh).pack(side="left"); ttk.Button(bar,text="Ekspor Penjualan CSV",command=self.export_sales).pack(side="left",padx=8)
        self.stree=self.tree(self.report,("invoice","created","payment","total"),("No. Transaksi","Waktu","Pembayaran","Total")); self.stree.pack(fill="both",expand=True,padx=10,pady=10)
    def refresh(self):
        for t in (self.ptree,self.stree):
            t.delete(*t.get_children())
        with connect() as c:
            for r in c.execute("SELECT code,barcode,name,category,price,stock FROM products ORDER BY name"): self.ptree.insert("","end",values=tuple(r))
            for r in c.execute("SELECT invoice,created,payment,total FROM sales ORDER BY id DESC"): self.stree.insert("","end",values=tuple(r))
    def add_cart(self):
        q=self.search.get().strip()
        with connect() as c: r=c.execute("SELECT * FROM products WHERE code=? OR barcode=? OR name LIKE ? LIMIT 1",(q,q,"%"+q+"%")).fetchone()
        if not r: messagebox.showwarning("SeaMart","Barang tidak ditemukan"); return
        for x in self.cart:
            if x["id"]==r["id"]: x["qty"]+=1; break
        else: self.cart.append(dict(id=r["id"],name=r["name"],qty=1,price=r["price"],cost=r["cost"],stock=r["stock"]))
        self.search.set(""); self.draw_cart()
    def draw_cart(self):
        self.carttree.delete(*self.carttree.get_children()); total=0
        for x in self.cart:
            n=x["qty"]*x["price"]; total+=n; self.carttree.insert("","end",values=(x["name"],x["qty"],f"{x['price']:,.0f}",f"{n:,.0f}"))
        self.total=total; self.totalvar.set(f"Total: Rp{total:,.0f}")
    def clear(self): self.cart=[]; self.draw_cart()
    def pay(self,method):
        if not self.cart: messagebox.showinfo("SeaMart","Keranjang masih kosong"); return
        total=self.total
        if method=="Tunai":
            from tkinter.simpledialog import askfloat
            received=askfloat("Pembayaran Tunai",f"Total Rp{total:,.0f}\nUang diterima:",minvalue=total)
            if received is None:return
        else: received=total
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"); invoice="SM"+datetime.now().strftime("%Y%m%d%H%M%S")
        with connect() as c:
            cur=c.execute("INSERT INTO sales(invoice,created,payment,subtotal,discount,total,received,change_due) VALUES(?,?,?,?,?,?,?,?)",(invoice,now,method,total,0,total,received,received-total)); sid=cur.lastrowid
            for x in self.cart:
                p=c.execute("SELECT stock FROM products WHERE id=?",(x["id"],)).fetchone()
                if p["stock"]<x["qty"]: messagebox.showerror("Stok","Stok tidak cukup untuk "+x["name"]); c.rollback(); return
                c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,cost,line_total) VALUES(?,?,?,?,?,?,?)",(sid,x["id"],x["name"],x["qty"],x["price"],x["cost"],x["qty"]*x["price"]))
                c.execute("UPDATE products SET stock=stock-? WHERE id=?",(x["qty"],x["id"]))
                c.execute("INSERT INTO movements(created,product_id,kind,qty,note) VALUES(?,?,?,?,?)",(now,x["id"],"PENJUALAN",-x["qty"],invoice))
        messagebox.showinfo("Transaksi berhasil",f"{invoice}\n{method}\nTotal Rp{total:,.0f}\nKembali Rp{received-total:,.0f}")
        self.cart=[]; self.draw_cart(); self.refresh()
    def add_product(self):
        from tkinter.simpledialog import askstring,askfloat
        name=askstring("Barang baru","Nama barang:")
        if not name:return
        price=askfloat("Harga","Harga jual:",minvalue=0)
        if price is None:return
        code=askstring("Kode","Kode produk (kosong=otomatis):") or "P"+datetime.now().strftime("%H%M%S%f")
        try:
            with connect() as c:c.execute("INSERT INTO products(code,name,price) VALUES(?,?,?)",(code,name,price))
            self.refresh()
        except Exception as e:messagebox.showerror("Gagal",str(e))
    def import_csv(self):
        p=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not p:return
        count=0
        try:
            with open(p,encoding="utf-8-sig",newline="") as f:
                for r in csv.DictReader(f):
                    name=r.get("nama") or r.get("Produk") or r.get("name")
                    if not name:continue
                    code=r.get("kode_produk") or r.get("Kode Produk") or r.get("code") or "P"+str(count+1)
                    barcode=r.get("barcode") or r.get("Barcode") or None
                    price=float((r.get("harga_jual") or r.get("Harga Jual") or r.get("price") or "0").replace(".","").replace(",",""))
                    stock=float((r.get("stok") or r.get("Stok") or r.get("stock") or "0").replace(",","."))
                    cat=r.get("kategori") or r.get("Grup Produk") or "Umum"
                    with connect() as c:c.execute("INSERT INTO products(code,barcode,name,category,price,stock) VALUES(?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET barcode=excluded.barcode,name=excluded.name,category=excluded.category,price=excluded.price,stock=excluded.stock",(code,barcode,name,cat,price,stock))
                    count+=1
            self.refresh(); messagebox.showinfo("Impor CSV",f"{count} barang berhasil diproses")
        except Exception as e:messagebox.showerror("Impor gagal",str(e))
    def export_csv(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        with connect() as c: rows=c.execute("SELECT name,barcode,price,stock,category,code FROM products").fetchall()
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["nama","barcode","harga_jual","stok","kategori","kode_produk"]); w.writerows([tuple(r) for r in rows])
        messagebox.showinfo("Ekspor","File CSV tersimpan")
    def export_sales(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        with connect() as c: rows=c.execute("SELECT invoice,created,payment,total FROM sales ORDER BY id DESC").fetchall()
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(["invoice","tanggal","pembayaran","total"]);w.writerows([tuple(r) for r in rows])
        messagebox.showinfo("Ekspor","File CSV tersimpan")

if __name__=="__main__":
    init(); SeaMart().mainloop()
