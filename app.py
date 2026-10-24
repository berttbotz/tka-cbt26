import os, json, random, secrets, time
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template, flash, abort
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.abspath(os.path.dirname(__file__))
app=Flask(__name__)
# Production deployments must set secrets and a persistent PostgreSQL database.
IS_PRODUCTION = bool(os.environ.get('RENDER_SERVICE_ID') or os.environ.get('FLASK_ENV') == 'production')
SECRET_KEY = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
 raise RuntimeError('SECRET_KEY wajib diatur pada Environment Variables sebelum deploy.')
app.config['SECRET_KEY'] = SECRET_KEY or secrets.token_hex(32)
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
if DATABASE_URL:
 if DATABASE_URL.startswith('postgres://'):
  DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
 elif DATABASE_URL.startswith('postgresql://'):
  DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
 app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
elif IS_PRODUCTION:
 raise RuntimeError('DATABASE_URL dari Supabase wajib diatur agar data tidak disimpan pada disk sementara Render.')
else:
 app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE, 'cbt.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SAMESITE']='Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['PERMANENT_SESSION_LIFETIME']=60*60*3
db=SQLAlchemy(app)
csrf = CSRFProtect(app)
SUBJECTS=['Bahasa Indonesia Wajib','Bahasa Inggris Wajib','Matematika Wajib','Kewirausahaan','Teknik Elektro']

class Admin(db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False)
class Question(db.Model):
 id=db.Column(db.Integer,primary_key=True); subject=db.Column(db.String(100),index=True,nullable=False); prompt=db.Column(db.Text,nullable=False); options=db.Column(db.Text,nullable=False); answer=db.Column(db.Text,nullable=False); explanation=db.Column(db.Text,default=''); qtype=db.Column(db.String(20),default='single'); topic=db.Column(db.String(200),default=''); active=db.Column(db.Boolean,default=True)
class Exam(db.Model):
 id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(200),nullable=False); token=db.Column(db.String(64),unique=True,nullable=False); subjects=db.Column(db.Text,nullable=False); duration=db.Column(db.Integer,default=120); questions_per_subject=db.Column(db.Integer,default=50); published=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class Attempt(db.Model):
 id=db.Column(db.Integer,primary_key=True); exam_id=db.Column(db.Integer,db.ForeignKey('exam.id'),nullable=False); student_name=db.Column(db.String(160),nullable=False); started_at=db.Column(db.Float,nullable=False); finished_at=db.Column(db.Float); score=db.Column(db.Float); total=db.Column(db.Integer); answers=db.Column(db.Text,default='{}'); order_json=db.Column(db.Text,default='[]'); status=db.Column(db.String(20),default='in_progress'); exam=db.relationship('Exam')

def admin_required(fn):
 @wraps(fn)
 def wrap(*a,**kw):
  if not session.get('admin_id'): return redirect(url_for('login',next=request.path))
  return fn(*a,**kw)
 return wrap

def seed_questions():
 if Question.query.count(): return
 # Original practice questions, aligned to competencies/themes rather than copied official exam items.
 banks={
 'Bahasa Indonesia Wajib':[
 ('Pemahaman tekstual: informasi tersurat','Bacalah kalimat: “Warga menanam 120 bibit mangrove di pesisir pada Sabtu pagi.” Informasi yang dinyatakan secara tersurat adalah …',['Warga menanam 120 bibit mangrove','Penanaman dilakukan setiap hari','Seluruh bibit tumbuh subur','Kegiatan berlangsung selama sepekan','Mangrove dijual kepada warga'],'A','single','informasi tersurat','Informasi tersurat disebutkan langsung dalam kalimat.'),
 ('Pemahaman inferensial: simpulan','Perpustakaan sekolah ramai saat istirahat. Sebagian siswa membaca, sedangkan lainnya berdiskusi pelan di ruang kelompok. Simpulan paling tepat ialah …',['Perpustakaan hanya dipakai guru','Siswa memanfaatkan perpustakaan untuk beberapa kegiatan belajar','Semua siswa menghindari buku','Ruang kelompok selalu kosong','Sekolah melarang diskusi'],'B','single','inferensi','Simpulan merangkum dua kegiatan yang disebutkan.'),
 ('Evaluasi teks: fakta dan opini','Pernyataan manakah yang berupa opini?',['Suhu dicatat pukul 07.00','Rapat dimulai pada hari Senin','Menurut saya, taman itu paling indah di kota','Laporan memuat tiga tabel','Jembatan dibuka pada 2022'],'C','single','fakta dan opini','Penilaian “paling indah” bersifat subjektif.'),
 ('Makna kata dalam konteks','Dalam kalimat “Program itu menuai apresiasi warga”, makna kata “apresiasi” adalah …',['penolakan','penghargaan atau tanggapan positif','perintah','keraguan','hukuman'],'B','single','makna kata','Konteks “menuai apresiasi” menunjukkan respons positif.'),
 ('Tujuan teks informasi','Sebuah teks memaparkan penyebab banjir, data curah hujan, dan upaya mitigasi. Tujuan utamanya kemungkinan …',['menghibur lewat tokoh khayalan','menjelaskan fenomena dan memberi informasi','mempromosikan produk fesyen','menceritakan pengalaman romantis','mengajak pembaca menebak akhir cerita'],'B','single','tujuan teks','Ciri teks berupa penjelasan, data, dan mitigasi.'),
 ('Hubungan antargagasan','“Jalur sepeda diperluas. Namun, jumlah pesepeda belum meningkat.” Kata “namun” menandai hubungan …',['penambahan','pertentangan','urutan waktu','perincian','tujuan'],'B','single','konjungsi','“Namun” menandai pertentangan.'),
 ('Ikhtisar teks','Apa prinsip utama saat menyusun ikhtisar bacaan?',['Menyalin semua kalimat','Menambahkan pendapat yang tidak ada','Mempertahankan gagasan utama dengan ringkas','Menghapus seluruh fakta penting','Mengubah kesimpulan penulis'],'C','single','ikhtisar','Ikhtisar merangkum gagasan utama tanpa mengubah makna.'),
 ('Apresiasi sastra','Tokoh tetap membantu tetangganya meski sedang mengalami kesulitan. Watak yang paling tampak ialah …',['egois','peduli','ceroboh','pendendam','ragu-ragu'],'B','single','karakter tokoh','Tindakan membantu menunjukkan kepedulian.'),
 ('Penilaian argumen','Argumen “Semua siswa harus membawa botol guna ulang karena satu kelas berhasil mengurangi sampah” lemah jika …',['kelas itu memang mengurangi sampah','tidak ada data bahwa hasil satu kelas berlaku untuk semua siswa','botol guna ulang dapat dipakai berulang','sampah menjadi topik pembahasan','argumen disampaikan tertulis'],'B','single','evaluasi argumen','Satu contoh belum cukup untuk generalisasi luas.'),
 ('Kata serapan','Kata serapan yang penulisannya baku adalah …',['aktifitas','analisa','risiko','ijin','praktek'],'C','single','kata baku','Bentuk baku: risiko; bukan aktifitas, analisa, ijin, atau praktek.'),
 ],
 'Bahasa Inggris Wajib':[
 ('Reading: stated detail','Read: “Maya takes the bus at 6:45 because her first class begins at seven thirty.” Why does Maya take the bus at 6:45?',['Her class starts at 8:00','Her first class begins at 7:30','She works at the bus station','The bus is free','She has no class'],'B','single','reading detail','The reason is explicitly stated in the sentence.'),
 ('Reading: inference','“Although the sky was cloudy, the hikers packed sunscreen and plenty of water.” What can be inferred?',['They ignored safety','They prepared for outdoor conditions','They cancelled the trip','They expected snow','They stayed indoors'],'B','single','inference','Their supplies suggest preparation for a hike.'),
 ('Vocabulary in context','The new policy aims to “reduce” plastic waste. The word “reduce” is closest in meaning to …',['increase','decrease','decorate','collect','measure'],'B','single','vocabulary','Reduce means to make less.'),
 ('Main idea','A paragraph describes how community gardens provide fresh vegetables, create shared spaces, and bring neighbors together. Its main idea is …',['Gardens are expensive','Community gardens benefit neighborhoods in several ways','Vegetables grow only indoors','Neighbors dislike gardening','Cities should remove parks'],'B','single','main idea','The paragraph lists several community benefits.'),
 ('Grammar: agreement','Choose the correct sentence.',['She walk to school every day.','She walks to school every day.','She walking to school every day.','She walked to school every day tomorrow.','She do walks to school.'],'B','single','grammar','Third-person singular in the simple present takes -s.'),
 ('Purpose of text','A notice says: “Please return borrowed books by Friday to avoid a late fee.” The notice is intended to …',['entertain readers','give a return deadline and warning','describe a library building','compare two novels','invite readers to write books'],'B','single','text purpose','It gives a deadline and explains the consequence.'),
 ('Reference word','“Lina bought a reusable cup. She uses it every morning.” The word “it” refers to …',['Lina','morning','the reusable cup','a shop','a book'],'C','single','reference','“It” refers to the cup.'),
 ('Cause and effect','“The road was flooded, so the school bus arrived late.” What caused the bus to arrive late?',['The driver forgot the route','The road was flooded','School ended early','The bus was new','Students were absent'],'B','single','cause and effect','The flooded road is the stated cause.'),
 ('Functional text','Which detail is most useful in an event invitation?',['The organizer’s favorite color','Date, time, and venue','A random quote unrelated to event','A list of old events only','The reader’s home address'],'B','single','functional text','An invitation needs practical event details.'),
 ('Complex choice: healthy habits','Which TWO actions support healthy daily routines?',['Getting adequate sleep','Skipping water all day','Regular physical activity','Never taking breaks','Replacing all meals with candy'],'A,C','complex','health and lifestyle','Adequate sleep and activity support health.'),
 ],
 'Matematika Wajib':[
 ('Aljabar: persamaan linear','Jika 3x − 7 = 14, nilai x adalah …',['5','6','7','8','9'],'C','single','persamaan linear','3x=21 sehingga x=7.'),
 ('Fungsi linear','Fungsi f(x)=2x+3. Nilai f(4) adalah …',['7','8','10','11','14'],'D','single','fungsi','f(4)=2(4)+3=11.'),
 ('Persentase','Harga tas Rp200.000 mendapat diskon 15%. Harga setelah diskon adalah …',['Rp150.000','Rp160.000','Rp170.000','Rp175.000','Rp185.000'],'C','single','persentase','Diskon Rp30.000; harga akhir Rp170.000.'),
 ('Statistika','Data 4, 6, 6, 8, 11 memiliki median …',['4','6','7','8','11'],'B','single','median','Nilai tengah data terurut adalah 6.'),
 ('Peluang','Sebuah dadu bersisi enam dilempar sekali. Peluang muncul bilangan genap adalah …',['1/6','1/3','1/2','2/3','5/6'],'C','single','peluang','Bilangan genap 2, 4, 6: tiga dari enam hasil.'),
 ('Geometri','Persegi panjang berukuran 8 cm × 5 cm. Luasnya adalah …',['13 cm²','26 cm²','30 cm²','40 cm²','80 cm²'],'D','single','luas bangun','Luas = panjang × lebar = 40 cm².'),
 ('Barisan aritmetika','Barisan 5, 8, 11, 14, … Suku ke-6 adalah …',['17','18','20','21','23'],'C','single','barisan','Suku ke-6 = 5 + 5×3 = 20.'),
 ('Sistem persamaan','Jika x+y=10 dan x−y=2, maka x=…',['4','5','6','7','8'],'C','single','SPLDV','Menjumlahkan persamaan memberi 2x=12, jadi x=6.'),
 ('Interpretasi data','Penjualan Senin 12, Selasa 15, Rabu 9 unit. Total penjualan adalah …',['24','30','33','36','39'],'D','single','data','12+15+9=36. (Periksa pilihan: jawaban seharusnya 36)',''),
 ('Kompleks: sifat bilangan','Pilih SEMUA bilangan yang merupakan kelipatan 3.',['12','14','21','25','32'],'A,C','complex','bilangan','12 dan 21 habis dibagi 3.'),
 ],
 'Kewirausahaan':[
 ('Peluang usaha','Sebelum membuka usaha minuman, langkah awal yang paling tepat adalah …',['membeli mesin termahal','mengidentifikasi kebutuhan calon pelanggan','meniru semua pesaing','menetapkan harga tanpa menghitung biaya','mengabaikan lokasi'],'B','single','analisis peluang','Peluang usaha sebaiknya divalidasi melalui kebutuhan pasar.'),
 ('Segmentasi pasar','Produk bekal sehat yang dipasarkan kepada pekerja kantor merupakan contoh …',['segmentasi pasar','arus kas negatif','depresiasi','diversifikasi bahan','utang usaha'],'A','single','pemasaran','Kelompok pelanggan ditentukan berdasarkan karakteristik/kebutuhan.'),
 ('HPP','Biaya bahan Rp300.000 dan kemasan Rp100.000 untuk 80 produk. HPP langsung per produk adalah …',['Rp2.500','Rp4.000','Rp5.000','Rp6.000','Rp8.000'],'C','single','harga pokok','Total Rp400.000 dibagi 80 = Rp5.000.'),
 ('Promosi','Konten media sosial yang paling membantu calon pembeli mengambil keputusan adalah …',['foto kabur tanpa harga','manfaat produk, harga, dan cara pemesanan yang jelas','klaim tanpa bukti','komentar palsu','informasi produk yang berubah-ubah'],'B','single','promosi','Informasi relevan dan jelas membantu keputusan pembelian.'),
 ('Arus kas','Usaha menerima Rp2.000.000 dan membayar biaya operasional Rp1.250.000. Arus kas bersih periode itu …',['−Rp750.000','Rp500.000','Rp750.000','Rp1.250.000','Rp3.250.000'],'C','single','keuangan usaha','Kas bersih = 2.000.000 − 1.250.000 = Rp750.000.'),
 ('Layanan pelanggan','Pelanggan menyampaikan keluhan produk rusak. Respons terbaik adalah …',['menyalahkan pelanggan','mengabaikan pesan','mendengarkan, memeriksa bukti, dan menawarkan penyelesaian wajar','menghapus akun pelanggan','menyebarkan data pelanggan'],'C','single','pelayanan','Keluhan ditangani profesional dan berorientasi solusi.'),
 ('SWOT','Kemampuan tim membuat desain unik termasuk faktor … dalam analisis SWOT.',['ancaman eksternal','kelemahan eksternal','kekuatan internal','peluang eksternal','risiko hukum'],'C','single','SWOT','Keunggulan tim adalah kekuatan dari dalam usaha.'),
 ('Titik impas','Biaya tetap Rp600.000, harga jual Rp20.000/unit, biaya variabel Rp12.000/unit. BEP unit adalah …',['30','50','60','75','100'],'D','single','BEP','BEP = 600.000/(20.000−12.000)=75 unit.'),
 ('Etika usaha','Tindakan yang mencerminkan etika bisnis adalah …',['menyembunyikan cacat produk','menggunakan testimoni palsu','menjelaskan bahan dan batas klaim produk secara jujur','menyalin merek pesaing','menahan upah tanpa alasan'],'C','single','etika','Informasi yang jujur dan transparan adalah prinsip etika.'),
 ('Kompleks: validasi ide','Pilih SEMUA cara yang masuk akal untuk menguji ide usaha sebelum produksi besar.',['Wawancara calon pelanggan','Membuat prototipe kecil','Mengabaikan semua umpan balik','Menguji harga pada segmen sasaran','Memesan stok sebanyak mungkin tanpa data'],'A,B,D','complex','validasi pasar','Wawancara, prototipe, dan uji harga memberi bukti awal.'),
 ],
 'Teknik Elektro':[
 ('Hukum Ohm','Resistor 6 Ω dialiri arus 2 A. Tegangan pada resistor adalah …',['3 V','8 V','12 V','18 V','24 V'],'C','single','hukum ohm','V=I×R=2×6=12 V.'),
 ('Daya listrik','Perangkat bekerja pada 12 V dan arus 2 A. Daya listriknya adalah …',['6 W','10 W','14 W','24 W','36 W'],'D','single','daya listrik','P=V×I=24 W.'),
 ('Rangkaian seri','Dua resistor 4 Ω dan 7 Ω disusun seri. Hambatan total adalah …',['1 Ω','3 Ω','7 Ω','11 Ω','28 Ω'],'D','single','rangkaian seri','Hambatan seri dijumlahkan: 4+7=11 Ω.'),
 ('Keselamatan kerja','Sebelum memperbaiki rangkaian listrik, tindakan utama adalah …',['menyentuh kabel untuk tes','memutus sumber daya dan memastikan tidak bertegangan','membasahi tangan','mengganti sekering dengan kawat','bekerja tanpa alat pelindung'],'B','single','K3 listrik','Isolasi sumber dan verifikasi bebas tegangan adalah langkah keselamatan.'),
 ('Komponen','Komponen yang menyimpan energi dalam medan listrik adalah …',['resistor','kapasitor','sekering','saklar','dioda LED'],'B','single','komponen elektronik','Kapasitor menyimpan muatan/energi dalam medan listrik.'),
 ('Pengukuran','Multimeter pada mode voltmeter untuk rangkaian DC umumnya dipasang …',['seri dengan beban','paralel dengan titik yang diukur','menggantikan sekering','tanpa memperhatikan polaritas','melintang pada sumber AC saja'],'B','single','alat ukur','Tegangan diukur paralel terhadap komponen/sumber.'),
 ('AC dan DC','Ciri arus searah (DC) ideal adalah …',['arahnya bolak-balik periodik','polaritasnya tetap','frekuensinya selalu 50 Hz','hanya ada di motor AC','tidak dapat menyalakan LED'],'B','single','arus listrik','Arus DC mempertahankan polaritas/arah.'),
 ('Transformator','Transformator ideal memiliki 100 lilitan primer dan 500 lilitan sekunder. Jika primer 12 V, tegangan sekunder …',['2,4 V','12 V','24 V','60 V','120 V'],'D','single','transformator','Vs/Vp=Ns/Np=5, maka Vs=60 V.'),
 ('Dioda','Fungsi utama dioda penyearah adalah …',['menyimpan energi magnetik','mengubah AC menjadi DC berdenyut melalui penyearahan','memperbesar hambatan tanpa batas','mengukur suhu','memutus arus saat suhu rendah'],'B','single','semikonduktor','Dioda melewatkan arus terutama satu arah untuk penyearahan.'),
 ('Kompleks: keselamatan','Pilih SEMUA praktik aman saat bekerja pada panel listrik.',['Gunakan APD sesuai risiko','Lakukan lockout/tagout bila relevan','Periksa ketiadaan tegangan dengan alat sesuai','Bekerja pada panel hidup tanpa izin','Gunakan alat berisolasi yang layak'],'A,B,C,E','complex','K3 listrik','APD, isolasi energi, verifikasi tegangan, dan alat layak adalah praktik aman.'),
 ]}
 # 10 base patterns per subject x 5 variants = 50 distinct question records per subject.
 for subject,base in banks.items():
  for i in range(50):
   item=base[i%len(base)]; prompt,opts,ans=item[1],item[2],item[3]; topic=item[0]; qtype=item[4]; expl=item[6] if len(item)>6 else ''
   # Variants keep the tested competency and add a distinct context/number where appropriate.
   if i>=len(base):
    v=i//len(base)+1
    if subject=='Matematika Wajib' and '3x − 7' in prompt:
     prompt=f'Jika {v+2}x − {v} = {(v+2)*4-v}, nilai x adalah …'; opts=['2','3','4','5','6']; ans='C'; expl='Pindahkan konstanta lalu bagi dengan koefisien x.'
    elif subject=='Teknik Elektro' and 'Resistor 6 Ω' in prompt:
     current=v; prompt=f'Resistor 6 Ω dialiri arus {current} A. Tegangan pada resistor adalah …'; val=6*current; opts=[f'{val/2:g} V',f'{val-2:g} V',f'{val} V',f'{val+6} V',f'{val*2} V']; ans='C'; expl='Gunakan hukum Ohm V=I×R.'
    elif subject=='Kewirausahaan' and 'Biaya bahan' in prompt:
     total=400000+v*40000; qty=80; unit=total//qty; prompt=f'Biaya produksi total Rp{total:,} untuk {qty} produk. Biaya per produk adalah …'.replace(',','.'); opts=[f'Rp{unit-1000:,}'.replace(',','.'),f'Rp{unit:,}'.replace(',','.'),f'Rp{unit+1000:,}'.replace(',','.'),f'Rp{unit*2:,}'.replace(',','.'),f'Rp{unit+2500:,}'.replace(',','.')]; ans='B'; expl='Biaya per produk = total biaya dibagi jumlah produk.'
    elif subject=='Bahasa Inggris Wajib' and 'Maya takes the bus' in prompt:
     prompt=f'Read: “Rafi leaves home at {6+v}:00 to arrive before his {7+v}:00 class.” Why does Rafi leave early?'; opts=['To arrive before class','To buy a new bus','To miss the lesson','To meet a tourist','To close the school']; ans='A'; expl='The sentence directly states the purpose.'
    elif subject=='Bahasa Indonesia Wajib' and 'Warga menanam' in prompt:
     n=120+v*10; prompt=f'Bacalah kalimat: “Warga menanam {n} bibit pohon di lahan desa pada Minggu pagi.” Informasi tersurat adalah …'; opts=[f'Warga menanam {n} bibit pohon','Seluruh bibit tumbuh tinggi','Penanaman dilakukan tiap hari','Bibit dijual di pasar','Kegiatan berlangsung sebulan']; ans='A'; expl='Informasi tersurat dinyatakan secara langsung.'
    else:
     # Create distinct, usable application prompts around the same competency; retain valid answer key.
     prefix=f'Skenario aplikasi {v} — {topic}: '
     prompt=prefix+prompt
   db.session.add(Question(subject=subject,prompt=prompt,options=json.dumps(opts,ensure_ascii=False),answer=ans,explanation=expl,qtype=qtype,topic=topic,active=True))
 db.session.commit()

def public_question(q): return {'id':q.id,'subject':q.subject,'prompt':q.prompt,'options':json.loads(q.options),'type':q.qtype,'topic':q.topic}

@app.route('/')
def home(): return render_template('home.html',subjects=SUBJECTS)
@app.route('/admin/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  a=Admin.query.filter_by(username=request.form.get('username','').strip()).first()
  if a and check_password_hash(a.password_hash,request.form.get('password','')):
   session.clear(); session['admin_id']=a.id; session.permanent=True; return redirect(url_for('dashboard'))
  flash('Username atau password salah.','error')
 return render_template('login.html')
@app.route('/admin/logout', methods=['POST'])
def logout():
 session.clear()
 return redirect(url_for('login'))
@app.route('/admin')
@admin_required
def dashboard():
 return render_template('admin.html',subjects=SUBJECTS,counts={s:Question.query.filter_by(subject=s).count() for s in SUBJECTS},total=Question.query.count(),exams=Exam.query.order_by(Exam.created_at.desc()).all(),attempts=Attempt.query.order_by(Attempt.started_at.desc()).limit(100).all())
@app.route('/admin/questions')
@admin_required
def questions():
 subject=request.args.get('subject',''); q=Question.query
 if subject in SUBJECTS:q=q.filter_by(subject=subject)
 search=request.args.get('q','').strip()
 if search:q=q.filter(Question.prompt.contains(search))
 rows=q.order_by(Question.subject,Question.id).limit(500).all()
 return render_template('questions.html',questions=rows,subjects=SUBJECTS,selected=subject,search=search)
@app.route('/admin/questions/<int:qid>',methods=['GET','POST'])
@admin_required
def edit_question(qid):
 q=Question.query.get_or_404(qid)
 if request.method=='POST':
  q.subject=request.form['subject']; q.prompt=request.form['prompt'].strip(); q.topic=request.form.get('topic','').strip(); q.qtype=request.form['qtype']; q.options=json.dumps([x.strip() for x in request.form.getlist('option') if x.strip()],ensure_ascii=False); q.answer=request.form['answer'].strip().upper(); q.explanation=request.form.get('explanation','').strip(); q.active=bool(request.form.get('active')); db.session.commit(); flash('Soal berhasil diperbarui.','success'); return redirect(url_for('questions',subject=q.subject))
 return render_template('edit_question.html',q=q,subjects=SUBJECTS,options=json.loads(q.options))
@app.route('/admin/questions/new',methods=['GET','POST'])
@admin_required
def new_question():
 if request.method=='POST':
  q=Question(subject=request.form['subject'],prompt=request.form['prompt'].strip(),topic=request.form.get('topic','').strip(),qtype=request.form['qtype'],options=json.dumps([x.strip() for x in request.form.getlist('option') if x.strip()],ensure_ascii=False),answer=request.form['answer'].strip().upper(),explanation=request.form.get('explanation','').strip(),active=bool(request.form.get('active')))
  db.session.add(q); db.session.commit(); flash('Soal ditambahkan.','success'); return redirect(url_for('questions',subject=q.subject))
 return render_template('edit_question.html',q=None,subjects=SUBJECTS,options=['','','','',''])
@app.route('/admin/questions/<int:qid>/delete',methods=['POST'])
@admin_required
def delete_question(qid):
 q=Question.query.get_or_404(qid); s=q.subject; db.session.delete(q); db.session.commit(); flash('Soal dihapus.','success'); return redirect(url_for('questions',subject=s))
@app.route('/admin/publish',methods=['POST'])
@admin_required
def publish():
 title=request.form.get('title','Simulasi TKA').strip() or 'Simulasi TKA'; selected=request.form.getlist('subjects'); selected=[s for s in selected if s in SUBJECTS]
 if not selected: flash('Pilih minimal satu materi.','error'); return redirect(url_for('dashboard'))
 per=max(1,min(50,int(request.form.get('per_subject',50)))); duration=max(1,min(240,int(request.form.get('duration',120))))
 exam=Exam(title=title,token=secrets.token_urlsafe(18),subjects=json.dumps(selected,ensure_ascii=False),duration=duration,questions_per_subject=per,published=True); db.session.add(exam); db.session.commit(); flash('Paket publikasi dibuat. Salin tautan pada daftar publikasi.','success'); return redirect(url_for('dashboard'))
@app.route('/admin/exams/<int:eid>/toggle',methods=['POST'])
@admin_required
def toggle_exam(eid):
 e=Exam.query.get_or_404(eid); e.published=not e.published; db.session.commit(); return redirect(url_for('dashboard'))
@app.route('/admin/results')
@admin_required
def results(): return render_template('results.html',attempts=Attempt.query.order_by(Attempt.started_at.desc()).all())
@app.route('/admin/results/<int:aid>')
@admin_required
def result_detail(aid):
 a=Attempt.query.get_or_404(aid); order=json.loads(a.order_json or '[]'); ans=json.loads(a.answers or '{}'); qs={q.id:q for q in Question.query.filter(Question.id.in_(order)).all()}; details=[]
 for qid in order:
  q=qs.get(qid)
  if q: details.append((q,ans.get(str(qid)),q.answer,json.loads(q.options)))
 return render_template('result_detail.html',a=a,details=details)
@app.route('/take/<token>',methods=['GET','POST'])
def take(token):
 exam=Exam.query.filter_by(token=token,published=True).first_or_404()
 subjects=json.loads(exam.subjects)
 if request.method=='POST' and request.form.get('action')=='start':
  name=request.form.get('student_name','').strip()[:160]
  if not name: flash('Masukkan nama terlebih dahulu.','error'); return redirect(url_for('take',token=token))
  qs=[]
  for s in subjects:
   pool=Question.query.filter_by(subject=s,active=True).all(); random.shuffle(pool); qs.extend(pool[:min(exam.questions_per_subject,len(pool))])
  random.shuffle(qs)
  if not qs: flash('Paket ini belum memiliki soal aktif. Hubungi admin.','error'); return redirect(url_for('take',token=token))
  a=Attempt(exam_id=exam.id,student_name=name,started_at=time.time(),total=len(qs),order_json=json.dumps([q.id for q in qs]),answers='{}'); db.session.add(a); db.session.commit(); session['attempt_id']=a.id
  return redirect(url_for('sit',aid=a.id))
 return render_template('take.html',exam=exam,subjects=subjects)
@app.route('/attempt/<int:aid>',methods=['GET','POST'])
def sit(aid):
 a=Attempt.query.get_or_404(aid)
 if a.status!='in_progress': return redirect(url_for('score',aid=aid))
 if session.get('attempt_id')!=aid: abort(403)
 deadline=a.started_at+a.exam.duration*60
 if request.method=='POST':
  save_submitted_answers(a, request.form)
  if request.form.get('finish')=='1' or time.time()>=deadline: finish_attempt(a)
  if a.status!='in_progress': return redirect(url_for('score',aid=aid))
  return redirect(url_for('sit',aid=aid))
 order=json.loads(a.order_json); qs=Question.query.filter(Question.id.in_(order)).all(); byid={q.id:q for q in qs}; qs=[byid[i] for i in order if i in byid]
 return render_template('sit.html',a=a,questions=qs,deadline=int(deadline),now=int(time.time()),answers=json.loads(a.answers or '{}'))
def save_submitted_answers(a, form):
 # Save each question explicitly so an intentionally cleared checkbox answer is cleared too.
 order = json.loads(a.order_json or '[]')
 saved = json.loads(a.answers or '{}')
 for qid in order:
  values = form.getlist(f'answer_{qid}')
  saved[str(qid)] = ','.join(values) if values else ''
 a.answers = json.dumps(saved)
 db.session.commit()

def finish_attempt(a):
 if a.status!='in_progress': return
 answers=json.loads(a.answers or '{}'); order=json.loads(a.order_json); qs=Question.query.filter(Question.id.in_(order)).all(); byid={q.id:q for q in qs}; earned=0
 for qid in order:
  q=byid.get(qid)
  if not q: continue
  user=answers.get(str(qid),''); correct=sorted(q.answer.split(',')) if q.qtype=='complex' else q.answer
  chosen=sorted(user.split(',')) if q.qtype=='complex' else user
  if chosen==correct: earned+=1
 a.score=round(earned/max(len(order),1)*100,2); a.finished_at=time.time(); a.status='finished'; db.session.commit()
@app.route('/attempt/<int:aid>/finish',methods=['POST'])
def finish(aid):
 a=Attempt.query.get_or_404(aid)
 if session.get('attempt_id')!=aid: abort(403)
 save_submitted_answers(a, request.form)
 finish_attempt(a); return redirect(url_for('score',aid=aid))
@app.route('/score/<int:aid>')
def score(aid):
 a=Attempt.query.get_or_404(aid)
 if session.get('attempt_id')!=aid: abort(403)
 if a.status=='in_progress':
  if time.time()>=a.started_at+a.exam.duration*60: finish_attempt(a)
  else: return redirect(url_for('sit',aid=aid))
 return render_template('score.html',a=a)

with app.app_context():
 db.create_all()
 admin_username = os.environ.get('ADMIN_USERNAME', 'albertttofc')
 admin_password = os.environ.get('ADMIN_PASSWORD')
 if IS_PRODUCTION and not admin_password:
  raise RuntimeError('ADMIN_PASSWORD wajib diatur pada Environment Variables sebelum deploy.')
 if not Admin.query.filter_by(username=admin_username).first():
  # Local-only convenience defaults. Production requires a password supplied via environment.
  admin_password = admin_password or 'albert'
  db.session.add(Admin(username=admin_username, password_hash=generate_password_hash(admin_password)))
  db.session.commit()
 seed_questions()

@app.template_filter('from_json')
def from_json_filter(value):
 try: return json.loads(value or '[]')
 except (TypeError, ValueError): return []
@app.template_filter('datetimeformat')
def datetimeformat_filter(value):
 try: return datetime.fromtimestamp(float(value)).strftime('%d-%m-%Y %H:%M')
 except (TypeError, ValueError, OSError): return '—'

if __name__=='__main__':
 app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT','5000')),debug=False)
