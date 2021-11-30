from PyQt5 import QtSql
from PyQt5 import QtWidgets
import sqlite3,pyodbc,phonenumbers
import config as cfg
import time

LOCAL_DB = "mikran.sqlite"

def create_con():
    con = QtSql.QSqlDatabase.addDatabase("QSQLITE")
    con.setDatabaseName("mikran.sqlite")
    return con

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS config (config_id INTEGER PRIMARY KEY, silican_address var_char(255), silican_port INTEGER, login var_char(255), password var_char(255), server var_char(255), database var_char(255), username var_char(255), passwd varchar(255))")
    data = (0,'192.168.0.2','5529','201','mikran123','192.168.0.140','MIKRAN','mikran_com','mikran_comqwer4321')
    try:
        c.execute("INSERT INTO config VALUES (?,?,?,?,?,?,?,?,?)", data)
    except:
        pass

    c.execute("CREATE TABLE IF NOT EXISTS users (adr_id INTEGER, adr_CountryCode varchar(10), tel_Numer varchar(255) UNIQUE, pa_Nazwa varchar(255), adr_NazwaPelna var_char(1024), adr_NIP varchar(255), adr_Miejscowosc varchar(255), adr_Ulica varchar(255), adr_Adres varchar(1024))")

    try:
        c.execute("CREATE UNIQUE INDEX idx_users_tel ON users (tel_Numer)")
    except:
        pass

    c.execute("CREATE TABLE IF NOT EXISTS current_calls ( cr INTEGER PRIMARY KEY, start_time TEXT, calls_state var_char(255), calling_number varchar(255), called_number varchar(255), FOREIGN KEY(calling_number) REFERENCES users(tel_Numer))")

    conn.commit()
    conn.close()

def load_config():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM config WHERE config_id=0")
    row = c.fetchone()
    config = dict(zip(row.keys(), row))
    conn.close()
    return config

def insert_users(users,signal):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()

    c.execute("DELETE FROM users")
    conn.commit()

    #for i in range(100):
    #    time.sleep(0.1)
    #    signal.emit((cfg.ODBC_INSERT,i))

    signal.emit((cfg.ODBC_INSERT_SETRANGE,len(users)))
    
    for idx,user in enumerate(users):
        signal.emit((cfg.ODBC_INSERT,idx))
        tel_Numer = user['tel_Numer']
    
        for match in phonenumbers.PhoneNumberMatcher(user['tel_Numer'], "PL"):
            tel_Numer = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
            tel_Numer = "".join(tel_Numer.split())
            adr_CountryCode = match.number.country_code
            
            try:
                c.execute("REPLACE INTO users (adr_id,tel_Numer,adr_CountryCode,pa_Nazwa, adr_NazwaPelna,adr_NIP,adr_Miejscowosc,adr_Ulica,adr_Adres) VALUES (%d,'%s','%s','%s','%s','%s','%s','%s','%s')" % (user['adr_Id'],tel_Numer,adr_CountryCode,user['pa_Nazwa'],user['adr_NazwaPelna'],user['adr_NIP'],user['adr_Miejscowosc'],user['adr_Ulica'],user['adr_Adres']))
            except sqlite3.IntegrityError as e:
                pass
            except Exception as e:
                print(str(e))

    signal.emit((cfg.ODBC_INSERT,0))
    conn.commit()
    conn.close()

def load_users(signal):
    config = load_config()

    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['passwd'])
    cursor = cnxn.cursor()

    cursor.execute("SELECT * FROM adr__Ewid LEFT JOIN sl_Panstwo ON adr__Ewid.adr_idPanstwo = sl_Panstwo.pa_id RIGHT JOIN tel__Ewid ON tel__Ewid.tel_IdAdresu = adr__Ewid.adr_Id WHERE adr__Ewid.adr_TypAdresu=1 ORDER BY adr_id ASC")
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    dict_rows = []
    for row in rows:
        dict_rows.append(dict(zip(columns, row)))

    cnxn.close()
    insert_users(dict_rows,signal)

def find_user(phonenumber):
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE instr(tel_Numer,'%s') > 0 OR instr('%s',tel_Numer) > 0" % (phonenumber,phonenumber))
    rows = c.fetchall()
    for row in rows:
        row = dict(zip(row.keys(), row))
        return row

    conn.close()

    return None
