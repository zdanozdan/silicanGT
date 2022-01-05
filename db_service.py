import pyodbc

config = {'server':'192.168.0.140','database':'SILICAN','username':'mikran_com','password':'mikran_comqwer4321'}

def init_db():
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['password'])
    cursor = cnxn.cursor()

    try:
        cursor.execute("CREATE TABLE config (silican_address varchar(255), silican_port INTEGER, login varchar(255), password varchar(255), sip_login varchar(64),sip_password varchar(64),sip_ip varchar(65))")
        cursor.commit()
    except:
        pass

    try:
        cursor.execute("CREATE TABLE voip_calls ( call_id varchar(255), start_time TEXT, calling_number varchar(255), call_to varchar(255), call_from varchar(255), call_received INTEGER, start_time_unix INTEGER)")
        cursor.commit()
    except:
        pass

    try:
        cursor.execute("CREATE TABLE current_calls ( cr INTEGER PRIMARY KEY, start_time TEXT, calls_state varchar(255), calling_number varchar(255), called_number varchar(255), login varchar(32),start_time_unix INTEGER)")
        cursor.commit()
    except:
        pass

    cnxn.close()

def load_config():
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['password'])
    cursor = cnxn.cursor()
    row = cursor.execute("SELECT * FROM config")
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row.fetchone()))

def execute(sql):
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['password'])
    cursor = cnxn.cursor()
    cursor.execute(sql)
    cursor.commit()
    
