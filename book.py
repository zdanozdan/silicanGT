from sip import SIPSession
import db,config
import pyodbc,phonenumbers
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time,re,datetime,threading
import sqlite3,logging
import db_service

LOCAL_DB = "mikran.sqlite"

logging.basicConfig(filename='service_log.txt', level=logging.ERROR)

def load_subiekt_config():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM config WHERE config_id=0")
    row = c.fetchone()
    config = dict(zip(row.keys(), row))
    conn.close()
    return config

def load_subiekt_users(config):
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['passwd'])
    cursor = cnxn.cursor()

    cursor.execute("SELECT * FROM adr__Ewid LEFT JOIN sl_Panstwo ON adr__Ewid.adr_idPanstwo = sl_Panstwo.pa_id RIGHT JOIN tel__Ewid ON tel__Ewid.tel_IdAdresu = adr__Ewid.adr_Id WHERE adr__Ewid.adr_TypAdresu=1 ORDER BY adr_id DESC")
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    dict_rows = []
    for row in rows:
        dict_rows.append(dict(zip(columns, row)))

    return dict_rows
    
class SilicanListener:

    def start(self,login,password,config):
        self.cursor = db_service.init_db()
        self.config = config
        silican_starter = threading.Thread(target=self.silican_listener, args=(login,password))
        silican_starter.start()
    
    def connect(self):
        self.config = db_service.load_config(self.cursor)
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.config['silican_address'],self.config['silican_port']))
            self.sock.settimeout(None)
        except Exception as e:
            print(str(e))
            logging.error("connect() : ", exc_info=True)

    def load_users(self):
        users = load_subiekt_users(load_subiekt_config())    
        loaded = []

        for row in users:
            for match in phonenumbers.PhoneNumberMatcher(row['adr_Telefon'], "PL"):
                tel_Numer = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
                tel_Numer = "".join(tel_Numer.split())
                adr_CountryCode = match.number.country_code
                tel = str(adr_CountryCode)+str(tel_Numer)
                if tel not in loaded:
                    phone = '''
                    <Phone>
                    <Number>%s</Number>
                    <Comment>G..wny</Comment>
                    <CmtType>Main</CmtType>
                    <DefaultNo>1</DefaultNo>
                    </Phone>
                    <Phone>
                    <Number>%s</Number>
                    <Comment>G..wny</Comment>
                    <CmtType>Main</CmtType>
                    <DefaultNo>1</DefaultNo>
                    </Phone>
                    ''' % (tel_Numer, tel)
                    #csv.append(silican_csv % (row['adr_Nazwa'],tel_Numer,tel,row['adr_NazwaPelna']))
                    self.add_contact_req(row['adr_Nazwa'],phone,row['adr_NazwaPelna'])
                    print("Loading ....",row['adr_Nazwa'],tel)
                    loaded.append(tel)
                    elem = self.read_frame()

    def sendall(self,message):
        try:
            self.sock.sendall(message)
        except Exception as e:
            logging.error("sendall() : ", exc_info=True)

    def login(self,login,password):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (login,password)
        self.sendall(message.encode('UTF-8'))

    def register_req(self):
        message = b'<XCTIP><Calls><Register_REQ><CId>1</CId></Register_REQ></Calls></XCTIP>'
        self.sendall(message)

    def permission_req(self):
        message = b'<XCTIP><Sync><GetPermission_REQ><CId>12</CId><Id>1001</Id></GetPermission_REQ></Sync></XCTIP>';
        self.sendall(message)

    def sync_book_req(self,marker=''):
        #message = b'<XCTIP><Sync><Sync_REQ><CId>12</CId><Id>1001</Id><Marker>BG0000FDD0000000025FB3AD3203E97C</Marker><SyncType>Book</SyncType><Limit>1</Limit></Sync_REQ></Sync></XCTIP>'
        message = '<XCTIP><Sync><Sync_REQ><CId>12</CId><Id>1001</Id><Marker>%s</Marker><SyncType>Book</SyncType><Limit>1</Limit></Sync_REQ></Sync></XCTIP>' % marker
        self.sendall(message.encode('UTF-8'))

    def delete_book_req(self,contact_id = 20):
        message ='<XCTIP><Sync><SendChange_REQ><CId>1</CId><Id>1001</Id><Row><RowType>DelRow</RowType><Contact><ContactId>%s</ContactId></Contact></Row></SendChange_REQ></Sync></XCTIP>' % contact_id
        self.sendall(message.encode('UTF-8'))

    def add_group_req(self):
        message = b'''<XCTIP>
        <Sync>
        <SendChange_REQ>
        <CId>1</CId>
        <Row>
        <RowType>AddRow</RowType>
        <SyncType>Book</SyncType>
        <Group>
        <Name>Subiekt</Name>
        <Favourite>0</Favourite>
        <Private>0</Private>
        </Group>
        </Row>
        </SendChange_REQ>
        </Sync>
        </XCTIP>'''
        self.sendall(message)

    def add_contact_req(self,name,phone_xml,opis=''):
        message = '''<XCTIP>
        <Sync>
        <SendChange_REQ>
        <CId>1</CId>
        <Id>1001</Id>
        <Row>
        <RowType>AddRow</RowType>
        <SyncType>Book</SyncType>
        <Contact>
        <Name>%s</Name>
        <Favourite>1</Favourite>
        <Private>0</Private>
        %s
        <GroupId>3</GroupId>
        <Info>%s</Info>
        </Contact>
        </Row>
        </SendChange_REQ>
        </Sync>
        </XCTIP>''' % (name,phone_xml,opis)
        self.sendall(message.encode('UTF-8'))

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            try:
                data = self.sock.recv(1)
                data = data.decode("utf-8")
                self.parser.feed(data)
                for event, elem in self.parser.read_events():
                    if elem.tag == 'XCTIP':
                        #print("READ FRAME",elem)
                        #ET.dump(elem)
                        return elem
            except ET.ParseError as e:
                pass

    def silican_listener(self,login,password):
        print("Silican thread started for login: :",login)
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login(login,password)
        #self.register_req()
        #self.permission_req()
        #self.add_group_req()

        self._login = login
        self.running = True        

        contact_id = 21
        while contact_id < 1000:
            try:
                #elem = self.read_frame()
                #self.delete_book_req(contact_id)
                contact_id = contact_id + 1
            except Exception as e:
                logging.error("SilicanConnectionThread() : ", exc_info=True)
                print("SilicanConnectionThread exception: ","SilicanConnectionThread: "+str(e))

        self.load_users()

            
if __name__ == "__main__":
    cursor = db_service.init_db()
    db_service.init_tables(cursor)

    config = db_service.load_config(cursor)
    
    #logins = config['login'].split(",")
    logins = ['201',]
    password = config['password']
    for login in logins:
        listener = SilicanListener()
        listener.start(login,password,config)
        time.sleep(1)
