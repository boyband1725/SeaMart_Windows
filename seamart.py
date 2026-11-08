import os, csv, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SeaMartPOS"
ROOT.mkdir(parents=True, exist_ok=True)
DB = ROOT / "seamart.db"

@contextmanager
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=ON")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY, code TEXT UNIQUE, barcode TEXT UNIQUE,
          name TEXT NOT NULL, category TEXT DEFAULT 'Umum', unit TEXT DEFAULT 'pcs',
          cost REAL DEFAULT 0, price REAL DEFAULT 0, stock REAL DEFAULT 0,
          min_stock REAL DEFAULT 0, non_stock INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sales(
          id INTEGER PRIMARY KEY, invoice TEXT UNIQUE, created TEXT, payment TEXT,
          subtotal REAL, discount REAL, total REAL, received REAL, change_due REAL,
          status TEXT DEFAULT 'LUNAS');
        CREATE TABLE IF NOT EXISTS sale_items(
          id INTEGER PRIMARY KEY, sale_id INTEGER REFERENCES sales(id),
          product_id INTEGER, name TEXT, qty REAL, price REAL, cost REAL, line_total REAL);
        CREATE TABLE IF NOT EXISTS movements(
          id INTEGER PRIMARY KEY, created TEXT, product_id INTEGER, kind TEXT,
          qty REAL, note TEXT);
        CREATE TABLE IF NOT EXISTS cashbook(
          id INTEGER PRIMARY KEY, created TEXT, kind TEXT, description TEXT, amount REAL);
        """)
        c.execute("INSERT OR IGNORE INTO products(code,name,category,price,stock) VALUES('DEMO-001','Contoh Barang','Umum',10000,10)")

def money(v):
    return "Rp" + format(float(v or 0), ",.0f")

class SeaMart(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SeaMart POS V15")
        self.geometry("1220x760")
        self.minsize(1000,650)
        self.configure(bg="#eef3f8")
        self.cart=[]
        self.style=ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=29, font=("Segoe UI",10))
        self.style.configure("Treeview.Heading", font=("Segoe UI",10,"bold"))
        top=tk.Frame(self,bg="#123c69",height=68); top.pack(fill="x")
        tk.Label(top,text="SeaMart",font=("Segoe UI",22,"bold"),fg="white",bg="#123c69").pack(side="left",padx=22,pady=12)
        tk.Label(top,text="POINT OF SALE  •  OFFLINE",font=("Segoe UI",10),fg="#dce9f6",bg="#123c69").pack(side="left",padx=8,pady=20)
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=12,pady=12)
        self.cash=tk.Frame(self.tabs,bg="#eef3f8")
        self.mastertab=tk.Frame(self.tabs,bg="#eef3f8")
        self.stocktab=tk.Frame(self.tabs,bg="#eef3f8")
        self.report=tk.Frame(self.tabs,bg="#eef3f8")
        self.cashbooktab=tk.Frame(self.tabs,bg="#eef3f8")
        for frame,label in [(self.cash,"Kasir"),(self.mastertab,"Master Barang"),(self.stocktab,"Stok & Mutasi"),(self.report,"Laporan"),(self.cashbooktab,"Kas Masuk/Keluar")]:
            self.tabs.add(frame,text=label)
        self.build_cash(); self.build_master(); self.build_stock(); self.build_reports(); self.build_cashbook()
        self.refresh_all()

    def tree(self,parent,cols,heads,width=130):
        wrap=tk.Frame(parent,bg="#eef3f8"); wrap.pack(fill="both",expand=True,padx=10,pady=8)
        t=ttk.Treeview(wrap,columns=cols,show="headings")
        for col,h in zip(cols,heads):
            t.heading(col,text=h); t.column(col,width=width,anchor="w")
        sy=ttk.Scrollbar(wrap,orient="vertical",command=t.yview); t.configure(yscrollcommand=sy.set)
        t.pack(side="left",fill="both",expand=True); sy.pack(side="right",fill="y")
        return t

    def build_cash(self):
        bar=tk.Frame(self.cash,bg="#eef3f8"); bar.pack(fill="x",padx=10,pady=12)
        self.search=tk.StringVar()
        ttk.Entry(bar,textvariable=self.search,width=42).pack(side="left",ipady=5)
        ttk.Button(bar,text="Tambah Barang",command=self.add_cart).pack(side="left",padx=7)
        ttk.Button(bar,text="Cari Kategori",command=self.pick_category).pack(side="left")
        self.carttree=self.tree(self.cash,("name","qty","price","total"),("Nama Barang","Qty","Harga","Jumlah"))
        foot=tk.Frame(self.cash,bg="#eef3f8"); foot.pack(fill="x",padx=12,pady=10)
        self.totalvar=tk.StringVar(value="TOTAL  Rp0")
        tk.Label(foot,textvariable=self.totalvar,bg="#eef3f8",fg="#123c69",font=("Segoe UI",20,"bold")).pack(side="left")
        ttk.Button(foot,text="Hapus Keranjang",command=self.clear_cart).pack(side="right",padx=4)
        ttk.Button(foot,text="Bayar QRIS",command=lambda:self.pay("QRIS")).pack(side="right",padx=4)
        ttk.Button(foot,text="Bayar Tunai",command=lambda:self.pay("Tunai")).pack(side="right",padx=4)

    def build_master(self):
        bar=tk.Frame(self.mastertab,bg="#eef3f8"); bar.pack(fill="x",padx=10,pady=10)
        for label,fn in [("Tambah Barang",self.add_product),("Impor CSV",self.import_csv),("Ekspor CSV",self.export_products),("Ekspor Excel",self.export_products_xlsx)]:
            ttk.Button(bar,text=label,command=fn).pack(side="left",padx=4)
        self.ptree=self.tree(self.mastertab,("code","barcode","name","category","unit","cost","price","stock"),("Kode","Barcode","Produk","Grup","Satuan","Modal","Jual","Stok"),110)

    def build_stock(self):
        bar=tk.Frame(self.stocktab,bg="#eef3f8"); bar.pack(fill="x",padx=10,pady=10)
        ttk.Button(bar,text="Stok Masuk / Penyesuaian",command=self.stock_adjust).pack(side="left",padx=4)
        ttk.Button(bar,text="Muat Ulang",command=self.refresh_stock).pack(side="left",padx=4)
        self.mtree=self.tree(self.stocktab,("created","name","kind","qty","note"),("Waktu","Barang","Jenis Mutasi","Perubahan","Catatan"),150)

    def build_reports(self):
        bar=tk.Frame(self.report,bg="#eef3f8"); bar.pack(fill="x",padx=10,pady=10)
        ttk.Button(bar,text="Muat Ulang",command=self.refresh_reports).pack(side="left",padx=4)
        ttk.Button(bar,text="Penjualan per Barang",command=self.sales_by_item).pack(side="left",padx=4)
        ttk.Button(bar,text="Ekspor Excel",command=self.export_report_xlsx).pack(side="left",padx=4)
        ttk.Button(bar,text="Ekspor PDF",command=self.export_report_pdf).pack(side="left",padx=4)
        ttk.Button(bar,text="Priveu Struk",command=self.preview_receipt).pack(side="left",padx=4)
        self.stree=self.tree(self.report,("invoice","created","payment","total","status"),("No. Transaksi","Tanggal","Pembayaran","Total","Status"),150)

    def build_cashbook(self):
        bar=tk.Frame(self.cashbooktab,bg="#eef3f8"); bar.pack(fill="x",padx=10,pady=10)
        ttk.Button(bar,text="Catat Kas Masuk",command=lambda:self.cash_entry("MASUK")).pack(side="left",padx=4)
        ttk.Button(bar,text="Catat Kas Keluar",command=lambda:self.cash_entry("KELUAR")).pack(side="left",padx=4)
        ttk.Button(bar,text="Ekspor CSV",command=self.export_cashbook).pack(side="left",padx=4)
        self.ctree=self.tree(self.cashbooktab,("created","kind","description","amount"),("Tanggal","Jenis","Keterangan","Jumlah"),170)

    def refresh_all(self):
        self.refresh_products(); self.refresh_stock(); self.refresh_reports(); self.refresh_cashbook()

    def refresh_products(self):
        self.ptree.delete(*self.ptree.get_children())
        with db() as c:
            for r in c.execute("SELECT code,barcode,name,category,unit,cost,price,stock FROM products ORDER BY category,name"):
                self.ptree.insert("","end",values=(r["code"],r["barcode"],r["name"],r["category"],r["unit"],money(r["cost"]),money(r["price"]),r["stock"]))

    def refresh_stock(self):
        self.mtree.delete(*self.mtree.get_children())
        with db() as c:
            rows=c.execute("SELECT m.created,p.name,m.kind,m.qty,m.note FROM movements m LEFT JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 500")
            for r in rows:self.mtree.insert("","end",values=tuple(r))

    def refresh_reports(self):
        self.stree.delete(*self.stree.get_children())
        with db() as c:
            for r in c.execute("SELECT invoice,created,payment,total,status FROM sales ORDER BY id DESC LIMIT 1000"):
                self.stree.insert("","end",values=(r["invoice"],r["created"],r["payment"],money(r["total"]),r["status"]))

    def refresh_cashbook(self):
        self.ctree.delete(*self.ctree.get_children())
        with db() as c:
            for r in c.execute("SELECT created,kind,description,amount FROM cashbook ORDER BY id DESC"):
                self.ctree.insert("","end",values=(r["created"],r["kind"],r["description"],money(r["amount"])))

    def add_cart(self):
        q=self.search.get().strip()
        if not q:return
        with db() as c:r=c.execute("SELECT * FROM products WHERE code=? OR barcode=? OR name LIKE ? LIMIT 1",(q,q,"%"+q+"%")).fetchone()
        if not r:messagebox.showwarning("SeaMart","Barang tidak ditemukan");return
        if not r["non_stock"] and r["stock"]<=0:messagebox.showwarning("Stok","Stok barang kosong");return
        for x in self.cart:
            if x["id"]==r["id"]:x["qty"]+=1;break
        else:self.cart.append(dict(id=r["id"],name=r["name"],qty=1,price=r["price"],cost=r["cost"],stock=r["stock"],non_stock=r["non_stock"]))
        self.search.set("");self.draw_cart()

    def pick_category(self):
        with db() as c:cats=[r[0] for r in c.execute("SELECT DISTINCT category FROM products ORDER BY category")]
        if not cats: return
        win=tk.Toplevel(self);win.title("Pilih Grup Produk");win.geometry("320x400")
        for cat in cats:
            ttk.Button(win,text=cat,command=lambda x=cat:(self.search.set(x),win.destroy(),self.search.focus_set())).pack(fill="x",padx=12,pady=5)

    def draw_cart(self):
        self.carttree.delete(*self.carttree.get_children());total=0
        for x in self.cart:
            line=x["qty"]*x["price"];total+=line
            self.carttree.insert("","end",values=(x["name"],x["qty"],money(x["price"]),money(line)))
        self.total=total;self.totalvar.set("TOTAL  "+money(total))

    def clear_cart(self):
        self.cart=[];self.draw_cart()

    def pay(self,method):
        if not self.cart:messagebox.showinfo("SeaMart","Keranjang masih kosong");return
        subtotal=sum(x["qty"]*x["price"] for x in self.cart)
        discount=simpledialog.askfloat("Diskon","Diskon transaksi (Rp), isi 0 jika tidak ada:",minvalue=0,initialvalue=0)
        if discount is None:return
        total=max(0,subtotal-discount)
        received=total
        if method=="Tunai":
            received=simpledialog.askfloat("Pembayaran Tunai","Total "+money(total)+"\nUang diterima:",minvalue=total)
            if received is None:return
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        invoice="SM"+datetime.now().strftime("%Y%m%d%H%M%S%f")
        with db() as c:
            for x in self.cart:
                p=c.execute("SELECT stock,non_stock FROM products WHERE id=?",(x["id"],)).fetchone()
                if not p["non_stock"] and p["stock"]<x["qty"]:
                    messagebox.showerror("Stok","Stok tidak cukup: "+x["name"]);return
            cur=c.execute("INSERT INTO sales(invoice,created,payment,subtotal,discount,total,received,change_due) VALUES(?,?,?,?,?,?,?,?)",(invoice,now,method,subtotal,discount,total,received,received-total))
            sid=cur.lastrowid
            for x in self.cart:
                c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,cost,line_total) VALUES(?,?,?,?,?,?,?)",(sid,x["id"],x["name"],x["qty"],x["price"],x["cost"],x["qty"]*x["price"]))
                if not x["non_stock"]:
                    c.execute("UPDATE products SET stock=stock-? WHERE id=?",(x["qty"],x["id"]))
                    c.execute("INSERT INTO movements(created,product_id,kind,qty,note) VALUES(?,?,?,?,?)",(now,x["id"],"PENJUALAN",-x["qty"],invoice))
            c.execute("INSERT INTO cashbook(created,kind,description,amount) VALUES(?,?,?,?)",(now,"MASUK","Penjualan "+invoice,total))
        self.last_invoice=invoice;self.last_receipt=(invoice,now,method,subtotal,discount,total,received,received-total,list(self.cart))
        self.cart=[];self.draw_cart();self.refresh_all()
        self.preview_receipt()
        messagebox.showinfo("SeaMart","Transaksi "+invoice+" berhasil disimpan.")

    def add_product(self):
        name=simpledialog.askstring("Barang Baru","Nama produk:")
        if not name:return
        code=simpledialog.askstring("Kode Produk","Kode produk:")
        if not code:return
        barcode=simpledialog.askstring("Barcode","Barcode (boleh kosong):") or None
        category=simpledialog.askstring("Grup Produk","Kategori:",initialvalue="Umum") or "Umum"
        unit=simpledialog.askstring("Satuan","Satuan:",initialvalue="pcs") or "pcs"
        cost=simpledialog.askfloat("Harga Pokok","Harga pokok:",minvalue=0) or 0
        price=simpledialog.askfloat("Harga Jual","Harga jual:",minvalue=0)
        if price is None:return
        stock=simpledialog.askfloat("Stok Awal","Stok awal:",minvalue=0) or 0
        try:
            with db() as c:
                cur=c.execute("INSERT INTO products(code,barcode,name,category,unit,cost,price,stock) VALUES(?,?,?,?,?,?,?,?)",(code,barcode,name,category,unit,cost,price,stock))
                if stock:c.execute("INSERT INTO movements(created,product_id,kind,qty,note) VALUES(?,?,?,?,?)",(datetime.now().isoformat(sep=" ",timespec="seconds"),cur.lastrowid,"STOK AWAL",stock,"Input barang"))
            self.refresh_all()
        except Exception as e:messagebox.showerror("Gagal",str(e))

    def import_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path:return
        count=0
        try:
            with open(path,encoding="utf-8-sig",newline="") as f:
                sample=f.read(4096);f.seek(0)
                dialect=csv.Sniffer().sniff(sample,delimiters=",;\t")
                reader=csv.DictReader(f,dialect=dialect)
                for row in reader:
                    r={str(k).strip().lower():str(v or "").strip() for k,v in row.items() if k}
                    def pick(*keys,default=""):
                        for k in keys:
                            if k.lower() in r and r[k.lower()]!="":return r[k.lower()]
                        return default
                    name=pick("produk","nama","name")
                    if not name:continue
                    code=pick("kode produk","kode_produk","code",default="CSV-"+str(count+1))
                    barcode=pick("barcode") or None
                    cat=pick("grup produk","kategori","category",default="Umum")
                    unit=pick("satuan","unit",default="pcs")
                    def num(v):
                        v=v.replace("Rp","").replace(" ","")
                        if "," in v and "." in v:v=v.replace(".","").replace(",",".")
                        elif "," in v:v=v.replace(",",".")
                        return float(v or 0)
                    cost=num(pick("harga pokok","harga_modal","cost",default="0"))
                    price=num(pick("harga jual","harga_jual","price",default="0"))
                    stock=num(pick("stok","stock",default="0"))
                    minimum=num(pick("stok minimum","stok_minimum","min_stock",default="0"))
                    nonstock=1 if pick("non stok","non_stok","nonstock",default="0").lower() in ("1","ya","yes","true") else 0
                    with db() as c:
                        c.execute("""INSERT INTO products(code,barcode,name,category,unit,cost,price,stock,min_stock,non_stock)
                        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET barcode=excluded.barcode,name=excluded.name,
                        category=excluded.category,unit=excluded.unit,cost=excluded.cost,price=excluded.price,
                        stock=excluded.stock,min_stock=excluded.min_stock,non_stock=excluded.non_stock""",
                        (code,barcode,name,cat,unit,cost,price,stock,minimum,nonstock))
                    count+=1
            self.refresh_all();messagebox.showinfo("Impor CSV",str(count)+" barang diproses.")
        except Exception as e:messagebox.showerror("Impor gagal",str(e))

    def export_products(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        with db() as c:rows=c.execute("SELECT name,cost,price,stock,category,unit,barcode,code,non_stock FROM products ORDER BY category,name").fetchall()
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(["Produk","Harga Pokok","Harga Jual","Stok","Grup Produk","Satuan","Barcode","Kode Produk","Non Stok"])
            for r in rows:w.writerow(tuple(r))
        messagebox.showinfo("Ekspor","CSV barang berhasil disimpan.")

    def stock_adjust(self):
        code=simpledialog.askstring("Mutasi Stok","Masukkan kode/barcode produk:")
        if not code:return
        qty=simpledialog.askfloat("Mutasi Stok","Jumlah perubahan (+ masuk, - keluar):")
        if qty is None or qty==0:return
        note=simpledialog.askstring("Catatan","Keterangan mutasi:",initialvalue="Penyesuaian stok") or ""
        with db() as c:
            p=c.execute("SELECT id,stock FROM products WHERE code=? OR barcode=?",(code,code)).fetchone()
            if not p:messagebox.showerror("Tidak ditemukan","Produk tidak ditemukan");return
            if p["stock"]+qty<0:messagebox.showerror("Stok","Stok tidak boleh negatif");return
            c.execute("UPDATE products SET stock=stock+? WHERE id=?",(qty,p["id"]))
            c.execute("INSERT INTO movements(created,product_id,kind,qty,note) VALUES(?,?,?,?,?)",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),p["id"],"PENYESUAIAN",qty,note))
        self.refresh_all()

    def cash_entry(self,kind):
        desc=simpledialog.askstring("Kas "+kind,"Keterangan:")
        if not desc:return
        amount=simpledialog.askfloat("Kas "+kind,"Jumlah Rupiah:",minvalue=0.01)
        if amount is None:return
        with db() as c:c.execute("INSERT INTO cashbook(created,kind,description,amount) VALUES(?,?,?,?)",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),kind,desc,amount))
        self.refresh_cashbook()

    def sales_by_item(self):
        win=tk.Toplevel(self);win.title("Rekap Penjualan per Barang");win.geometry("800x500")
        t=self.tree(win,("name","qty","sales"),("Nama Barang","Qty Terjual","Total Penjualan"),180)
        with db() as c:
            for r in c.execute("SELECT si.name,SUM(si.qty) qty,SUM(si.line_total) sales FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.status='LUNAS' GROUP BY si.name ORDER BY sales DESC"):
                t.insert("","end",values=(r["name"],r["qty"],money(r["sales"])))

    def export_products_xlsx(self):
        self._export_xlsx("barang")

    def export_report_xlsx(self):
        self._export_xlsx("penjualan")

    def _export_xlsx(self,kind):
        path=filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")])
        if not path:return
        try:
            from openpyxl import Workbook
            wb=Workbook();ws=wb.active;ws.title="SeaMart"
            with db() as c:
                if kind=="barang":
                    ws.append(["Produk","Harga Pokok","Harga Jual","Stok","Grup Produk","Satuan","Barcode","Kode Produk","Non Stok"])
                    rows=c.execute("SELECT name,cost,price,stock,category,unit,barcode,code,non_stock FROM products ORDER BY category,name")
                else:
                    ws.append(["Invoice","Tanggal","Pembayaran","Subtotal","Diskon","Total","Status"])
                    rows=c.execute("SELECT invoice,created,payment,subtotal,discount,total,status FROM sales ORDER BY id DESC")
                for r in rows:ws.append(list(r))
            wb.save(path);messagebox.showinfo("Ekspor","File Excel berhasil dibuat.")
        except Exception as e:messagebox.showerror("Ekspor Excel",str(e))

    def export_report_pdf(self):
        path=filedialog.asksaveasfilename(defaultextension=".pdf",filetypes=[("PDF","*.pdf")])
        if not path:return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            p=canvas.Canvas(path,pagesize=A4);w,h=A4;y=h-45
            p.setFont("Helvetica-Bold",16);p.drawString(40,y,"SeaMart - Laporan Penjualan");y-=30
            p.setFont("Helvetica",9)
            p.drawString(40,y,"Invoice");p.drawString(180,y,"Tanggal");p.drawString(330,y,"Metode");p.drawString(440,y,"Total");y-=18
            with db() as c:rows=c.execute("SELECT invoice,created,payment,total FROM sales ORDER BY id DESC").fetchall()
            for r in rows:
                if y<45:p.showPage();y=h-45;p.setFont("Helvetica",9)
                p.drawString(40,y,str(r["invoice"]));p.drawString(180,y,str(r["created"]));p.drawString(330,y,str(r["payment"]));p.drawRightString(550,y,money(r["total"]));y-=15
            p.save();messagebox.showinfo("Ekspor","PDF berhasil dibuat.")
        except Exception as e:messagebox.showerror("Ekspor PDF",str(e))

    def export_cashbook(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        with db() as c:rows=c.execute("SELECT created,kind,description,amount FROM cashbook ORDER BY id DESC").fetchall()
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(["tanggal","jenis","keterangan","jumlah"]);w.writerows([tuple(r) for r in rows])
        messagebox.showinfo("Ekspor","Buku kas berhasil diekspor.")

    def preview_receipt(self):
        if not getattr(self,"last_receipt",None):
            messagebox.showinfo("Struk","Belum ada transaksi pada sesi ini.");return
        inv,created,method,subtotal,discount,total,received,change,items=self.last_receipt
        win=tk.Toplevel(self);win.title("Pratinjau Struk 58mm");win.geometry("360x620")
        box=tk.Text(win,width=38,height=32,font=("Courier New",9));box.pack(fill="both",expand=True,padx=8,pady=8)
        lines=["             SeaMart","       STRUK PEMBELIAN","-"*32,inv,created,"Metode: "+method,"-"*32]
        for x in items:
            lines.extend([x["name"][:32],f'{x["qty"]:g} x {money(x["price"])} = {money(x["qty"]*x["price"])}'])
        lines.extend(["-"*32,"Subtotal : "+money(subtotal),"Diskon   : "+money(discount),"TOTAL    : "+money(total),"Diterima : "+money(received),"Kembali  : "+money(change),"","       Terima kasih"])
        box.insert("1.0","\n".join(lines));box.configure(state="disabled")
        ttk.Button(win,text="Tutup",command=win.destroy).pack(pady=6)

if __name__=="__main__":
    init_db()
    SeaMart().mainloop()
