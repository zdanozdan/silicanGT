import sqlite3,pyodbc,phonenumbers
LOCAL_DB = "mikran.sqlite"

def load_config():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM config WHERE config_id=0")
    row = c.fetchone()
    config = dict(zip(row.keys(), row))
    conn.close()
    return config

config = load_config()

cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+config['server']+';DATABASE='+config['database']+';UID='+config['username']+';PWD='+ config['passwd'])
cursor = cnxn.cursor()

cursor.execute("SELECT * FROM adr__Ewid LEFT JOIN sl_Panstwo ON adr__Ewid.adr_idPanstwo = sl_Panstwo.pa_id RIGHT JOIN tel__Ewid ON tel__Ewid.tel_IdAdresu = adr__Ewid.adr_Id WHERE adr__Ewid.adr_TypAdresu=1 ORDER BY adr_id ASC")
columns = [col[0] for col in cursor.description]
rows = cursor.fetchall()
dict_rows = []
for row in rows:
    dict_rows.append(dict(zip(columns, row)))

#nazwa 26 znaków
#First Name,Last Name,Primary Phone,Home Phone,Home Phone 2,Mobile Phone,Home Fax,Company Main Phone,Business Phone,Business Phone 2,Business Fax,Department,Other Phone,Other Fax,Private,Categories,Notes,E-mail 2 Address
#"Tomasz Zdanowski2","mikran.p","","","","","","","601570947","618475858","","","","","0","Slican WebCTI;Subiekt GT","Ta opcja menu grupuje kilka opcji, ktůre pozwalajĻ abonentowi na zarzĻdzanie us≥ugami dostÍpnymi dla niego",""

silican_csv = '"%s","","","","","","","","%s","","","","","","0","Slican WebCTI;Subiekt GT","%s",""'

print("First Name,Last Name,Primary Phone,Home Phone,Home Phone 2,Mobile Phone,Home Fax,Company Main Phone,Business Phone,Business Phone 2,Business Fax,Department,Other Phone,Other Fax,Private,Categories,Notes,E-mail 2 Address")

loaded = []

for row in dict_rows:
    for match in phonenumbers.PhoneNumberMatcher(row['adr_Telefon'], "PL"):
        tel_Numer = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
        tel_Numer = "".join(tel_Numer.split())
        adr_CountryCode = match.number.country_code
        tel = str(adr_CountryCode)+str(tel_Numer)
        if tel not in loaded:
            print(silican_csv % (row['adr_Nazwa'],tel,row['adr_NazwaPelna']))
        loaded.append(tel)
cnxn.close()
