import pyodbc

config = {'server':192.168.0.140,'database':'SILICAN','username':'mikran_com','password':'mikran_comqwer4321'}

def init_db():
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['passwd'])
    cursor = cnxn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS config (silican_address var_char(255), silican_port INTEGER, login var_char(255), password var_char(255), sip_login varchar(64),sip_password(64),sip_ip(65))")
    cnxn.close()
