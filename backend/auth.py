import os, sqlite3, secrets, hashlib, hmac, time
from pathlib import Path
DB_PATH=Path(os.getenv('AUTH_DB_PATH',str(Path(__file__).resolve().parent/'data'/'terminal.db'))); DB_PATH.parent.mkdir(parents=True,exist_ok=True)
def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def hash_password(p,it=210000):
    salt=secrets.token_bytes(16); d=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,it); return f'pbkdf2_sha256${it}${salt.hex()}${d.hex()}'
def verify_password(p,s):
    try:
        alg,it,salt,d=s.split('$'); calc=hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(salt),int(it)).hex(); return alg=='pbkdf2_sha256' and hmac.compare_digest(calc,d)
    except Exception:return False
def init_db():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,created_at REAL NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at REAL NOT NULL,created_at REAL NOT NULL)'); c.commit()
        u=os.getenv('ADMIN_USERNAME','owner'); p=os.getenv('ADMIN_PASSWORD','')
        if p and not c.execute('SELECT id FROM users WHERE username=?',(u,)).fetchone(): c.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)',(u,hash_password(p),'owner',time.time())); c.commit()
def authenticate(u,p):
    with db() as c:r=c.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone()
    return dict(r) if r and verify_password(p,r['password_hash']) else None
def create_session(uid,days=1):
    raw=secrets.token_urlsafe(32); now=time.time(); th=hashlib.sha256(raw.encode()).hexdigest()
    with db() as c:c.execute('DELETE FROM sessions WHERE expires_at<?',(now,)); c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(th,uid,now+days*86400,now)); c.commit()
    return raw
def get_user(token):
    if not token:return None
    th=hashlib.sha256(token.encode()).hexdigest()
    with db() as c:r=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?',(th,time.time())).fetchone()
    return dict(r) if r else None
def revoke(token):
    if token:
        with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)); c.commit()
