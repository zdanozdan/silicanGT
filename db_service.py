import pyodbc

config = {'server':'192.168.0.140','database':'SILICAN','username':'mikran_com','password':'mikran_comqwer4321'}


def init_db():
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['password'])
    cursor = cnxn.cursor()

    return cursor

def init_tables(cursor):

    try:
        cursor.execute("CREATE TABLE config (silican_address varchar(255), silican_port INTEGER, login varchar(255), password varchar(255), sip_login varchar(64),sip_password varchar(64),sip_ip varchar(65))")
        cursor.commit()
    except:
        pass

    try:
        cursor.execute("CREATE TABLE voip_calls ( call_id varchar(255), start_time TEXT, calling_number varchar(255), call_to varchar(255), call_from varchar(255), call_received varchar(64), start_time_unix INTEGER, silican_ringing varchar(255))")
        cursor.commit()
    except:
        pass

    try:
        cursor.execute("CREATE TABLE current_calls ( cr_id INTEGER NOT NULL IDENTITY(1,1) PRIMARY KEY, cr INTEGER , start_time TEXT, calls_state varchar(255), calling_number varchar(255), called_number varchar(255), login varchar(32),start_time_unix INTEGER, colp varchar(64),attempts INTEGER DEFAULT 1)")
        cursor.commit()
    except:
        pass


def load_config(cursor):
    row = cursor.execute("SELECT * FROM config")
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row.fetchone()))

def execute(cursor,sql):
    cursor.execute(sql)
    cursor.commit()    
