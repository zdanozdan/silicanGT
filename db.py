from PyQt5 import QtSql
from PyQt5 import QtWidgets
import sqlite3,pyodbc,phonenumbers

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

    c.execute("CREATE TABLE IF NOT EXISTS users (adr_id INTEGER, adr_CountryCode varchar(10), adr_Telefon varchar(255) UNIQUE, pa_Nazwa varchar(255), adr_NazwaPelna var_char(1024), adr_NIP varchar(255), adr_Miejscowosc varchar(255), adr_Ulica varchar(255), adr_Adres varchar(1024))")

    #['adr_Id', 'adr_IdObiektu', 'adr_TypAdresu', 'adr_Nazwa', 'adr_NazwaPelna', 'adr_Telefon', 'adr_Faks', 'adr_Ulica', 'adr_NrDomu', 'adr_NrLokalu', 'adr_Adres', 'adr_Kod', 'adr_Miejscowosc', 'adr_IdWojewodztwo', 'adr_IdPanstwo', 'adr_NIP', 'adr_Poczta', 'adr_Gmina', 'adr_Powiat', 'adr_Skrytka', 'adr_Symbol', 'adr_IdGminy', 'adr_IdWersja', 'adr_IdZmienil', 'adr_DataZmiany']
    
    conn.commit()

def load_config():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM config WHERE config_id=0")
    row = c.fetchone()
    config = dict(zip(row.keys(), row))
    return config

def insert_user(user):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    adr_Telefon = user['adr_Telefon']
    
    for match in phonenumbers.PhoneNumberMatcher(user['adr_Telefon'], "PL"):
        adr_Telefon = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
        adr_Telefon = "".join(adr_Telefon.split())
        adr_CountryCode = match.number.country_code
            
        try:
            c.execute("REPLACE INTO users (adr_id,adr_Telefon,adr_CountryCode,pa_Nazwa, adr_NazwaPelna,adr_NIP,adr_Miejscowosc,adr_Ulica,adr_Adres) VALUES (%d,'%s','%s','%s','%s','%s','%s','%s','%s')" % (user['adr_Id'],adr_Telefon,adr_CountryCode,user['pa_Nazwa'],user['adr_NazwaPelna'],user['adr_NIP'],user['adr_Miejscowosc'],user['adr_Ulica'],user['adr_Adres']))
            conn.commit()
        except Exception as e:
            print(str(e))

def load_users():

    config = load_config()

    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['passwd'])
    cursor = cnxn.cursor()
 
    cursor.execute("SELECT * FROM adr__Ewid LEFT JOIN sl_Panstwo ON adr__Ewid.adr_idPanstwo = sl_Panstwo.pa_id WHERE adr_TypAdresu=1 ORDER BY adr_id ASC")
    columns = [col[0] for col in cursor.description]
    print(columns)
    rows = cursor.fetchall()
    for row in rows:
        dict_row = dict(zip(columns, row))
        insert_user(dict_row)
  
