from PyQt5 import QtSql
from PyQt5 import QtWidgets
import sqlite3,pyodbc,phonenumbers
import config as cfg
import slack
import time
import csv,json

LOCAL_DB = "mikran.sqlite"

def create_con():
    con = QtSql.QSqlDatabase.addDatabase("QSQLITE")
    con.setDatabaseName("mikran.sqlite")
    return con

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS config (config_id INTEGER PRIMARY KEY, silican_address var_char(255), silican_port INTEGER, login var_char(255), password var_char(255), server var_char(255), database var_char(255), username var_char(255), passwd varchar(255), slack_token varchar(255), slack_url varchar(255))")

    try:
        c.execute("ALTER TABLE config ADD sip_login varchar(64)")
        c.execute("ALTER TABLE config ADD sip_password varchar(64)")
        c.execute("ALTER TABLE config ADD sip_ip varchar(64)")
    except:
        pass

    f = open('config.json','r')
    json_config = json.load(f)

    try:
        values = list(json_config.values())
        c.execute("INSERT INTO config VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
    except:
        pass

    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT sip_login,sip_password,sip_ip FROM config WHERE config_id=0")
        row = c.fetchone()
        config = dict(zip(row.keys(), row))
        if not config['sip_login'] and not config['sip_password'] and not config['sip_ip']:
            sql = "UPDATE config SET sip_login='%s',sip_password='%s',sip_ip='%s' WHERE config_id=0" % (json_config['sip_login'],json_config['sip_password'],json_config['sip_ip'])
            c.execute(sql)
    except:
        pass

    #try:
    #c.execute("DROP TABLE slack_users")
    c.execute("CREATE TABLE IF NOT EXISTS slack_users (userid varchar(255) UNIQUE, username varchar(255))")
    c.execute("DELETE FROM slack_users")
    #except:
    #    pass

    c.execute("CREATE TABLE IF NOT EXISTS users (adr_id INTEGER, adr_CountryCode varchar(10), tel_Numer varchar(255) UNIQUE, pa_Nazwa varchar(255), adr_NazwaPelna var_char(1024), adr_NIP varchar(255), adr_Miejscowosc varchar(255), adr_Ulica varchar(255), adr_Adres varchar(1024))")

    try:
        c.execute("CREATE UNIQUE INDEX idx_users_tel ON users (tel_Numer)")
        c.execute("ALTER TABLE users ADD column login varchar(32)")
    except:
        pass

    c.execute("CREATE TABLE IF NOT EXISTS current_calls ( cr INTEGER PRIMARY KEY, start_time TEXT, calls_state var_char(255), calling_number varchar(255), called_number varchar(255), FOREIGN KEY(calling_number) REFERENCES users(tel_Numer))")

    try:
        c.execute("ALTER TABLE current_calls ADD column login varchar(32)")
    except:
        pass

    try:
        c.execute("ALTER TABLE current_calls ADD column start_time_unix INTEGER")
    except:
        pass

    c.execute('CREATE TABLE IF NOT EXISTS history_calls (marker varchar(255), row_type var_char(32), sync_type varchar(255), hid INTEGER PRIMARY KEY, start_time TEXT, h_type  varchar(256), dial_number INTEGER, duration_time INTEGER, attempts INTEGER, calling_number varchar(255), cname varchar(255), FOREIGN KEY(calling_number) REFERENCES users(tel_Numer))')

    try:
        c.execute("ALTER TABLE history_calls ADD column login varchar(32)")
    except:
        pass

    try:
        c.execute("ALTER TABLE history_calls ADD column start_time_unix INTEGER")
    except:
        pass

    c.execute("CREATE TABLE IF NOT EXISTS voip_calls ( call_id varchar(255) PRIMARY KEY, start_time TEXT, calling_number varchar(255), call_to varchar(255), call_from varchar(255), FOREIGN KEY(calling_number) REFERENCES users(tel_Numer))")

    try:
        c.execute("ALTER TABLE voip_calls ADD column call_status INTEGER")
    except:
        pass

    try:
        c.execute("ALTER TABLE voip_calls ADD column cr INTEGER")
    except:
        pass

    try:
        c.execute("ALTER TABLE voip_calls ADD column calls_state varchar(255)")
    except:
        pass

    try:
        c.execute("ALTER TABLE voip_calls ADD column start_time_unix INTEGER")
    except:
        pass

    conn.commit()
    conn.close()

def deleteUsers():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("DELETE FROM users")
    conn.commit()
    conn.close()

def deleteCalls():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("DELETE FROM current_calls")
    conn.commit()
    conn.close()

def deleteHistory():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("DELETE FROM history_calls")
    conn.commit()
    conn.close()

def get_columns(select_query):
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(select_query)
    row = c.fetchone()
    keys = row.keys()
    conn.close()
    return keys

def get_last_marker():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT start_time,marker,hid FROM history_calls ORDER BY hid DESC")
    row = c.fetchone()
    conn.close()
    return row['marker']

def load_slack_users():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    users = slack.get_members()
    for user in users:
        c.execute("REPLACE INTO slack_users (username,userid) values('%s','%s')" % user)
    conn.commit()
    conn.close()
    return users

def slack_users_list():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute("SELECT * FROM slack_users")
    rows = c.fetchall()
    conn.close()
    return rows    

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

    #c.execute("DELETE FROM users")
    #conn.commit()

    signal.emit((cfg.ODBC_INSERT_SETRANGE,len(users)))
    
    for idx,user in enumerate(users):
        signal.emit((cfg.ODBC_INSERT,idx))
        tel_Numer = user['tel_Numer']
    
        for match in phonenumbers.PhoneNumberMatcher(user['tel_Numer'], "PL"):
            tel_Numer = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
            tel_Numer = "".join(tel_Numer.split())
            adr_CountryCode = match.number.country_code

            sql = "REPLACE INTO users (adr_id,tel_Numer,adr_CountryCode,pa_Nazwa, adr_NazwaPelna,adr_NIP,adr_Miejscowosc,adr_Ulica,adr_Adres) VALUES (%d,'%s','%s','%s','%s','%s','%s','%s','%s')" % (user['adr_Id'],tel_Numer,adr_CountryCode,user['pa_Nazwa'],user['adr_NazwaPelna'],user['adr_NIP'],user['adr_Miejscowosc'],user['adr_Ulica'],user['adr_Adres'])
            signal.emit((cfg.ODBC_SQL,sql))

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
    if len(str(phonenumber)) < 8:
        return None
    
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
