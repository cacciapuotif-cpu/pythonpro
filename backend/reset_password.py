import bcrypt
import os
import psycopg

password = 'Admin2026!'
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

db_url = os.getenv('DATABASE_URL', '')
db_url = db_url.replace('postgresql+psycopg://', '')
parts = db_url.split('@')
userpass = parts[0].split(':')
hostdb = parts[1].split('/')
hostport = hostdb[0].split(':')

conn = psycopg.connect(
    host=hostport[0],
    port=int(hostport[1]) if len(hostport) > 1 else 5432,
    dbname=hostdb[1],
    user=userpass[0],
    password=userpass[1],
)
cur = conn.cursor()
cur.execute(
    "UPDATE users SET hashed_password=%s WHERE email=%s RETURNING id",
    (hashed, 'admin@gestionale.local')
)
row = cur.fetchone()
conn.commit()
conn.close()
print('OK: aggiornato user id={}'.format(row[0]))
print('Nuova password: Admin2026!')
