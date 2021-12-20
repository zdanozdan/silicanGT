#!/usr/bin/env python3

import sys,socket,time,re
from sip import SIPSession

from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5 import QtSql

#XML
import xml.etree.ElementTree as ET
#sqlite
import sqlite3
import datetime,logging

import db,gt,config,silican,slack

logging.basicConfig(filename='logfile.txt', level=logging.ERROR)

VERSION_NUMBER = "1.4"

Q1 = "SELECT * FROM current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer ORDER BY start_time DESC"
Q1_LIMIT = "SELECT * FROM current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer LIMIT 1"

Q1_FILTER = "SELECT * FROM current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer WHERE %s ORDER BY start_time DESC"

Q2 = "SELECT * FROM history_calls LEFT JOIN users ON history_calls.calling_number = users.tel_Numer ORDER BY start_time DESC"

Q2_FILTER = "SELECT * FROM history_calls LEFT JOIN users ON history_calls.calling_number = users.tel_Numer WHERE %s ORDER BY start_time DESC"

Q2_LIMIT = "SELECT * FROM history_calls LEFT JOIN users ON history_calls.calling_number = users.tel_Numer LIMIT 1"

VOIP_QUERY = "SELECT * FROM voip_calls LEFT JOIN users ON voip_calls.calling_number = users.tel_Numer ORDER BY start_time DESC"
VOIP_QUERY_FILTER = "SELECT * FROM voip_calls LEFT JOIN users ON voip_calls.calling_number = users.tel_Numer where %s ORDER BY start_time DESC"
VOIP_QUERY_LIMIT = "SELECT * FROM voip_calls LEFT JOIN users ON voip_calls.calling_number = users.tel_Numer ORDER BY start_time DESC LIMIT 1"

class Window(QtWidgets.QMainWindow):
    _signal = pyqtSignal(tuple)
    
    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.setWindowTitle("mikran.pl - integracja centrali telefonicznej")
        print("mikran.pl - integracja centrali telefonicznej")
        self.setWindowIcon(QIcon('yoda.png')) 
        self.resize(800, 600)
        self.statusBar().showMessage('mikran.pl. Ready')
        self._calling_number = "..."
        db.init_db()
        self.config = db.load_config()

        self.voip_calls_columns = []
        try:
            self.voip_calls_columns = db.get_columns(VOIP_QUERY_LIMIT)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                "Error: %s" % str(e),
            )
        
        self.current_calls_columns = []
        try:
            self.current_calls_columns = db.get_columns(Q1_LIMIT)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                "Error: %s" % str(e),
            )
        self.history_calls_columns = []
        try:
            self.history_calls_columns = db.get_columns(Q2_LIMIT)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                "Error: %s" % str(e),
            )
        try:
            db.load_slack_users()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Slack error",
                "Slack Error: %s" % str(e),
            )
        self.con = db.create_con()
        if not self.con.open():
            QtWidgets.QMessageBox.critical(
                None,
                "Database error! Sprawdź ustawienia DB",
                "Database Error: %s" % con.lastError().databaseText(),
            )
            return

        self.addModels()
        self.addViews()

        vbox = QtWidgets.QVBoxLayout()
        self.phonenumber = QtWidgets.QLabel("Czekam na nowe połączenie ....")
        font = self.phonenumber.font()
        font.setPointSize(30)
        self.phonenumber.setFont(font)
        self.phonenumber.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.phonenumber.setStyleSheet("color: gray")
        vbox.addWidget(self.phonenumber)
        
        grid = QtWidgets.QGridLayout(self)
        
        grid.addWidget(QtWidgets.QLabel("Firma:"),0,0)
        self.firma = QtWidgets.QLabel("...")
        policy = self.firma.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        self.firma.setSizePolicy(policy)
        grid.addWidget(self.firma,0,1)

        grid.addWidget(QtWidgets.QLabel("Adres:"),1,0)
        self.adres = QtWidgets.QLabel("...")
        grid.addWidget(self.adres,1,1)

        grid.addWidget(QtWidgets.QLabel("NIP:"),2,0)
        self.nip = QtWidgets.QLabel("...")
        grid.addWidget(self.nip,2,1)
        vbox.addLayout(grid)
        self.addTabs(vbox)

        self.pbar = QtWidgets.QProgressBar(self)
        self.pbar.setValue(0)
        vbox.addWidget(self.pbar)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(vbox)
        self.setCentralWidget(self.widget)
        
        #self.createToolBar()
        self.createMenuBar()
        self.createSettingsWigdet()
        self.start_threads()

        self._signal.connect(self.self_signal)
        self.monitorVOIP()

        quit = QtWidgets.QAction("Quit", self)
        quit.triggered.connect(self.closeEvent)

    def self_signal(self,data):
        if data[0] == 'SQL':
            #print("Prepare SQL: " ,data[1])            
            query = QtSql.QSqlQuery()
            query.exec(data[1])
            self.voip_model.setQuery(QtSql.QSqlQuery(VOIP_QUERY))
            self.voip_model.select()
        if data[0] == "INFOLINE_NUMBER":
            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage('Nowe połączenie w kolejce infolini : %s' % data[1])
            self.phonenumber.setText("Na infolinii: %s" % data[1])
            self.phonenumber.setStyleSheet("color: blue")
        if data[0] == "INFOLINE_USER":
            adres = (data[1]['adr_Adres'],data[1]['adr_Miejscowosc'],data[1]['pa_Nazwa'])
            adres = ",".join(adres)
            nazwa = data[1]['adr_NazwaPelna']
            nip = data[1]['adr_NIP']
            number = data[1]['tel_Numer']

            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage('Pierwsze połączenie w kolejce infolini : %s (%s, %s, NIP: %s)' % (number,nazwa,adres,nip))

            self.firma.setText(nazwa)
            self.firma.setStyleSheet("color: blue")
            self.adres.setText(adres)
            self.adres.setStyleSheet("color: blue")
            self.nip.setText(nip)
            self.nip.setStyleSheet("color: blue")
            self.phonenumber.setText("Oczekuje na infolini: %s" % number)
            self.phonenumber.setStyleSheet("color: blue")

        if data[0] == "INFOLINE_BAD_REQUEST":
            self.statusBar().setStyleSheet("color: blue")
            self.statusBar().showMessage('Błąd rejestracji infolinii')
            QtWidgets.QMessageBox.critical(
                None,
                "Błąd",
                "Błąd infolinii: Bad request"
            )
            self.monitorVOIP()

    def monitorVOIP(self):
        if not self.config['sip_login'] or not self.config['sip_ip'] or not self.config['sip_password']:
            QtWidgets.QMessageBox.critical(
                None,
                "Błąd",
                "Brakuje konfiguracji infolinii, nie będzie można rejestorwać połączeń"
            )
        else:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            sip_session = SIPSession(local_ip,self.config['sip_login'],self.config['sip_ip'],self.config['sip_password'],account_port=5060,display_name="mikran")
            sip_session.call_ringing += self.voip_ringing
            sip_session.call_bad_request += self.voip_badrequest
            sip_session.send_sip_register()

    def voip_badrequest(self,session,data):
        self._signal.emit(("INFOLINE_BAD_REQUEST",data))

    def voip_ringing(self,session,data):
        #print("------------ RINGING START")
        #print(data)
        #print("RINGING STOP --------------")
        
        try:
            call_id = re.findall(r'Call-ID: (.*?)\r\n', data)
            call_id = call_id[0]
            call_to = re.findall(r'To: (.*?)\r\n', data)
            call_to = call_to[0]
            call_from = re.findall(r'From: (.*?)\r\n', data)
            call_from = call_from[0]
            calling_number = re.findall(r'sip:([0-9]+)', call_from)
            calling_number = calling_number[0]
            #print("RING:",call_id,call_to,call_from)
            #print("Number calling: ",calling_number)
        
            user = db.find_user(str(calling_number))
            if user:
                calling_number = user['tel_Numer']
                self._signal.emit(("INFOLINE_USER",user))
            else:
                self._signal.emit(("INFOLINE_NUMBER",calling_number))

            sql = "INSERT INTO voip_calls (call_id,start_time,calling_number,call_to,call_from,call_status) VALUES ('%s','%s','%s','%s','%s','%s')" % (call_id,datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calling_number,call_to,call_from,config.VOIP_NEW)
            self._signal.emit(("SQL",sql))
        except Exception as e:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage('Błąd podczs zapisu połączenia: %s' % str(e))
        
    def closeEvent(self,event):
        close = QtWidgets.QMessageBox()
        close.setText("Na pewno?")
        close.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
        close = close.exec()

        if close == QtWidgets.QMessageBox.Yes:
            self.stop_threads()
            event.accept()            
        else:
            event.ignore()
            
    def createMenuBar(self):
        usersAction = QtWidgets.QAction(QIcon('download.png'), '&Pobierz kontrahentów', self)
        usersAction.setShortcut('Ctrl+P')
        usersAction.setStatusTip('Pobierz konkrahentów z baz danych')
        usersAction.triggered.connect(self.usersActionThread)

        historyAction = QtWidgets.QAction(QIcon('history.png'), '&Pobierz historię (wew: '+self.config['login']+')', self)
        historyAction.setShortcut('Ctrl+I')
        historyAction.setStatusTip('Pobierz historię dla tego numeru wew')
        historyAction.triggered.connect(self.historyActionThread)

        settingsAction = QtWidgets.QAction(QIcon('settings.png'), '&Ustawienia', self)
        settingsAction.setShortcut('Ctrl+U')
        settingsAction.setStatusTip('UStawienia')
        settingsAction.triggered.connect(self.settings)
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&Plik')
        fileMenu.addAction(usersAction)
        fileMenu.addAction(historyAction)
        fileMenu.addAction(settingsAction)

        deleteUsersAction = QtWidgets.QAction(QIcon('delete.png'), '&Usuń kontrahentów', self)
        deleteUsersAction.triggered.connect(self.deleteUsers)

        deleteHistoryAction = QtWidgets.QAction(QIcon('delete.png'), '&Usuń historię połączeń', self)
        deleteHistoryAction.triggered.connect(self.deleteHistory)

        deleteCallsAction = QtWidgets.QAction(QIcon('delete.png'), '&Usuń bieżące połączenia', self)
        deleteCallsAction.triggered.connect(self.deleteCalls)

        advMenu = mainMenu.addMenu('&Zaawnsowane')
        advMenu.addAction(deleteUsersAction)
        advMenu.addAction(deleteHistoryAction)
        advMenu.addAction(deleteCallsAction)

        versionAction = QtWidgets.QAction(QIcon('delete.png'), '&Wersja', self)
        versionAction.triggered.connect(self.version)
        verMenu = mainMenu.addMenu('&Pomoc')
        verMenu.addAction(versionAction)

    def usersActionThread(self):
        gt_thread = gt.GTThread(parent=self)
        gt_thread._signal.connect(self.signal_gt)
        gt_thread.start()
        self.statusBar().setStyleSheet("color: green")
        self.statusBar().showMessage('Pobieranie listy kontrahentów ....')

    def historyActionThread(self):
        silican_history_thread = silican.SilicanHistoryThread(parent=self)
        silican_history_thread._signal.connect(self.signal_silican)
        silican_history_thread.start()

    def start_threads(self):
        self.silican_thread = silican.SilicanConnectionThread(parent=self)
        self.silican_thread._signal.connect(self.signal_silican)
        self.silican_thread.start()

        self.history_ev_thread = silican.SilicanHistoryEventsThread(parent=self)
        self.history_ev_thread._signal.connect(self.signal_silican)
        self.history_ev_thread.start()

    def stop_threads(self):
        self.silican_thread.stop()
        self.silican_thread.quit()
        self.silican_thread.wait()
        self.history_ev_thread.stop()
        self.history_ev_thread.quit()
        self.history_ev_thread.wait()

    def signal_silican(self,data):
        if data[0] == config.SILICAN_CONNECTED:
            self.statusBar().showMessage('Centrala podłączona')
        if data[0] == config.SILICAN_ERROR:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage('Błąd %s' % data[1])
            QtWidgets.QMessageBox.critical(
                None,
                "Błąd  %s" % data[1],
                "Błąd  %s" % data[1],
            )

        if data[0] == config.SILICAN_SUCCESS:
            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage('Sukces %s' % data[1])
            QtWidgets.QMessageBox.information(
                None,
                "Sukces  %s" % data[1],
                "Sukces  %s" % data[1],
            )

        if data[0] == config.SILICAN_USER_FOUND:
            adres = (data[1]['adr_Adres'],data[1]['adr_Miejscowosc'],data[1]['pa_Nazwa'])
            self.firma.setText(data[1]['adr_NazwaPelna'])
            self.firma.setStyleSheet("color: green")
            self.adres.setText(",".join(adres))
            self.adres.setStyleSheet("color: green")
            self.nip.setText(data[1]['adr_NIP'])
            self.nip.setStyleSheet("color: green")
            
        if data[0] == config.SILICAN_CONNECTION:
            self.phonenumber.setStyleSheet("color: green")
            self.phonenumber.setText("Nowe połączenie: %s" % data[1])
            self.firma.setText("...")
            self.adres.setText("...")
            self.nip.setText("...")
            self._calling_number = data[1]

        if data[0] == config.SILICAN_RELEASE:
            self.phonenumber.setText("Zakończono: %s" % self._calling_number)
            self.phonenumber.setStyleSheet("color: gray")
            self.firma.setStyleSheet("color: gray")
            self.adres.setStyleSheet("color: gray")
            self.nip.setStyleSheet("color: gray")

        if data[0] == config.SILICAN_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])
            self.calls_model.setQuery(QtSql.QSqlQuery(Q1))
            self.calls_model.select()

        if data[0] == config.SILICAN_PROGRESS:            
            self.pbar.setValue(int(data[1]))

        if data[0] == config.SILICAN_SETRANGE:
            self.pbar.setMaximum(int(data[1]))

        if data[0] == config.SILICAN_HISTORY_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])
            self.history_model.setQuery(QtSql.QSqlQuery(Q2))
            self.history_model.select()

    def signal_gt(self,data):
        if data[0] == config.ODBC_ERROR:
            QtWidgets.QMessageBox.critical(
                None,
                "GT connection error %s" % data[1],
                "GT connection error %s" % data[1],
            )

        if data[0] == config.ODBC_SUCCESS:
            self.users_model.setTable("users")
            self.users_model.select()
            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage("Pobrano kartoteki klientów")
            QtWidgets.QMessageBox.information(
                None,
                "Pobrano kartotetki klientów: %s" % data[1],
                "Pobrano kartoteki klientów: %s" % data[1],
            )

        if data[0] == config.ODBC_INSERT:
            self.pbar.setValue(int(data[1]))

        if data[0] == config.ODBC_INSERT_SETRANGE:
            self.pbar.setMaximum(int(data[1]))

        if data[0] == config.ODBC_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])

    def addModels(self):
        self.users_model = MikranTableModel(config=self.config)
        self.users_model.setTable("users")
        self.users_model.select()

        self.calls_model = MikranTableModel(config=self.config)
        self.calls_model.setQuery(QtSql.QSqlQuery(Q1))
        self.calls_model.select()

        self.history_model = MikranTableModel(config=self.config)
        self.history_model.setQuery(QtSql.QSqlQuery(Q2))
        self.history_model.select()

        self.voip_model = MikranTableModel(config=self.config)
        self.voip_model.setQuery(QtSql.QSqlQuery(VOIP_QUERY))
        self.voip_model.select()

    def addViews(self):
        self.tableview_history = CallsTableView(self.history_calls_columns)
        self.tableview_history.setAlternatingRowColors(True);
        self.tableview_history.setModel(self.history_model)
        self.tableview_history.resizeColumnsToContents()
        self.tableview_history.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_history.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_history.setSortingEnabled(True)
        self.tableview_history.setWordWrap(True);
        self.tableview_history.update()
        self.history_columns = {self.tableview_history.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_history.model().columnCount())}

        self.tableview_history.hideColumn(self.history_columns['marker'])
        self.tableview_history.hideColumn(self.history_columns['row_type'])
        self.tableview_history.hideColumn(self.history_columns['sync_type'])
        self.tableview_history.hideColumn(self.history_columns['hid'])
        self.tableview_history.hideColumn(self.history_columns['adr_id'])
        self.tableview_history.hideColumn(self.history_columns['adr_CountryCode'])
        self.tableview_history.hideColumn(self.history_columns['tel_Numer'])
        self.tableview_history.hideColumn(self.history_columns['pa_Nazwa'])
        self.tableview_history.hideColumn(self.history_columns['adr_Adres'])
        self.tableview_history.hideColumn(self.history_columns['cname'])
        self.tableview_history.hideColumn(self.history_columns['login'])

        self.tableview_history.model().setHeaderData(self.history_columns['start_time'], Qt.Horizontal, "Czas i data")
        self.tableview_history.model().setHeaderData(self.history_columns['h_type'], Qt.Horizontal, "Status")
        self.tableview_history.model().setHeaderData(self.history_columns['dial_number'], Qt.Horizontal, "Linia")
        self.tableview_history.model().setHeaderData(self.history_columns['duration_time'], Qt.Horizontal, "Czas połączenia")
        self.tableview_history.model().setHeaderData(self.history_columns['calling_number'], Qt.Horizontal, "Numer telefonu")
        self.tableview_history.model().setHeaderData(self.history_columns['attempts'], Qt.Horizontal, "Ilość prób")
        
        self.tableview_users = QtWidgets.QTableView()
        self.tableview_users.setAlternatingRowColors(True);
        #self.tableview_users.setStyleSheet("alternate-background-color: yellow;background-color: red;");
        self.tableview_users.setModel(self.users_model)
        self.tableview_users.resizeColumnsToContents()
        self.tableview_users.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_users.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_users.setSortingEnabled(True)
        self.tableview_users.setWordWrap(True);
        self.tableview_users.update()
        self.users_columns = {self.tableview_users.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_users.model().columnCount())}

        self.tableview_calls = CallsTableView(self.current_calls_columns)
        self.tableview_calls.setAlternatingRowColors(True);
        self.tableview_calls.setModel(self.calls_model)
        self.tableview_calls.resizeColumnsToContents()
        self.tableview_calls.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_calls.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_calls.setSortingEnabled(True)
        self.tableview_calls.setWordWrap(True);
        self.tableview_calls.update()
        self.calls_columns = {self.tableview_calls.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_calls.model().columnCount())}

        self.tableview_calls.hideColumn(self.calls_columns['cr'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_id'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_CountryCode'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_CountryCode'])
        self.tableview_calls.hideColumn(self.calls_columns['tel_Numer'])
        self.tableview_calls.hideColumn(self.calls_columns['pa_Nazwa'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_Adres'])
        self.tableview_calls.hideColumn(self.calls_columns['login'])
        #TODO
        #FIX - login pojawia się 2 krotnie z powodu Q1_LIMIT. Dict umożliwia tylko 1 klucz a mamy 2 kolumny o nazwie login i jedna (z nr 5) jest nadpisywana
        self.tableview_calls.hideColumn(5)

        self.tableview_calls.model().setHeaderData(self.calls_columns['start_time'], Qt.Horizontal, "Czas i data")
        self.tableview_calls.model().setHeaderData(self.calls_columns['calls_state'], Qt.Horizontal, "Status")
        self.tableview_calls.model().setHeaderData(self.calls_columns['called_number'], Qt.Horizontal, "Linia")
        self.tableview_calls.model().setHeaderData(self.calls_columns['calling_number'], Qt.Horizontal, "Nr telefonu")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_NazwaPelna'], Qt.Horizontal, "Nazwa")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_NIP'], Qt.Horizontal, "NIP")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_Miejscowosc'], Qt.Horizontal, "Miejscowość")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_Ulica'], Qt.Horizontal, "Ulica")

        self.tableview_voip = CallsTableView(self.voip_calls_columns)
        self.tableview_voip.setAlternatingRowColors(True);
        self.tableview_voip.setModel(self.voip_model)
        self.tableview_voip.resizeColumnsToContents()
        self.tableview_voip.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_voip.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_voip.setSortingEnabled(True)
        self.tableview_voip.setWordWrap(True);
        self.tableview_voip.update()

        self.voip_columns = {self.tableview_voip.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_voip.model().columnCount())}

        self.tableview_voip.hideColumn(self.voip_columns['call_id'])
        self.tableview_voip.hideColumn(self.voip_columns['call_to'])
        self.tableview_voip.hideColumn(self.voip_columns['call_from'])
        self.tableview_voip.hideColumn(self.voip_columns['adr_id'])
        self.tableview_voip.hideColumn(self.voip_columns['adr_CountryCode'])
        self.tableview_voip.hideColumn(self.voip_columns['adr_CountryCode'])
        self.tableview_voip.hideColumn(self.voip_columns['tel_Numer'])
        self.tableview_voip.hideColumn(self.voip_columns['pa_Nazwa'])
        self.tableview_voip.hideColumn(self.voip_columns['adr_Adres'])

        self.tableview_voip.model().setHeaderData(self.voip_columns['start_time'], Qt.Horizontal, "Czas i data")
        self.tableview_voip.model().setHeaderData(self.voip_columns['calling_number'], Qt.Horizontal, "Nr telefonu")
        self.tableview_voip.model().setHeaderData(self.voip_columns['call_status'], Qt.Horizontal, "Status")
        self.tableview_voip.model().setHeaderData(self.voip_columns['adr_NazwaPelna'], Qt.Horizontal, "Nazwa")
        self.tableview_voip.model().setHeaderData(self.voip_columns['adr_NIP'], Qt.Horizontal, "NIP")
        self.tableview_voip.model().setHeaderData(self.voip_columns['adr_Miejscowosc'], Qt.Horizontal, "Miejscowość")
        self.tableview_voip.model().setHeaderData(self.voip_columns['adr_Ulica'], Qt.Horizontal, "Ulica")

    def addTabs(self,vbox):
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tab3 = QtWidgets.QWidget()
        self.tab4 = QtWidgets.QWidget()
        self.tabs.addTab(self.tab1,"Bieżące połączenia ( wew "+self.config['login']+" )")
        self.tabs.addTab(self.tab2,"Historyczne dla ( wew "+self.config['login']+" )")
        self.tabs.addTab(self.tab3,"Kontakty")
        self.tabs.addTab(self.tab4,"Infolinia (61 8475858)")
        vbox.addWidget(self.tabs)

        layout = QtWidgets.QVBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.textChanged.connect(self.filter_users)
        layout.addWidget(line_edit)
        layout.addWidget(self.tableview_users)
        self.tab3.setLayout(layout)

        layout_calls = QtWidgets.QVBoxLayout()
        line_edit_calls = QtWidgets.QLineEdit()
        line_edit_calls.textChanged.connect(self.filter_calls)
        layout_calls.addWidget(line_edit_calls)
        layout_calls.addWidget(self.tableview_calls)
        self.tab1.setLayout(layout_calls)

        layout_history = QtWidgets.QVBoxLayout()
        line_edit_history = QtWidgets.QLineEdit()
        line_edit_history.textChanged.connect(self.filter_history)
        layout_history.addWidget(line_edit_history)
        layout_history.addWidget(self.tableview_history)
        self.tab2.setLayout(layout_history)

        layout_voip = QtWidgets.QVBoxLayout()
        line_edit_voip = QtWidgets.QLineEdit()
        line_edit_voip.textChanged.connect(self.filter_voip)
        layout_voip.addWidget(line_edit_voip)
        layout_voip.addWidget(self.tableview_voip)
        self.tab4.setLayout(layout_voip)
        
    def createSettingsWigdet(self):
        self.settings_widget = QtWidgets.QDialog()
        self.settings_widget.setWindowTitle("mikran.pl - ustawienia")
        self.settings_widget.setModal(True)
        model = QtSql.QSqlTableModel(self)
        model.setTable("config")  

        tableview = QtWidgets.QTableView()
        tableview.setModel(model)
        tableview.setSortingEnabled(True)
        tableview.sortByColumn(0, Qt.DescendingOrder);

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(tableview)

        btn = QtWidgets.QPushButton("Zamknij")
        btn.clicked.connect(self.settings_widget.close)
        vbox.addWidget(btn)
        
        self.settings_widget.setLayout(vbox)

    def createToolBar(self):
        toolBar = QtWidgets.QToolBar()
        self.addToolBar(toolBar)
        
        toolButton = QtWidgets.QToolButton()
        toolButton.setText("Settings")
        toolButton.clicked.connect(self.settings)
        toolBar.addWidget(toolButton)

    def _deleteFromTable(self,table,model,query):
        ret = QtWidgets.QMessageBox.question(self,'', "Na pewno usunąć ?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ret == QtWidgets.QMessageBox.Yes:
            query = QtSql.QSqlQuery()
            query.exec("DELETE FROM %s" % table)
            model.setQuery(query)
            model.select()

    def deleteUsers(self):
        ret = QtWidgets.QMessageBox.question(self,'', "Na pewno usunąć ?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ret == QtWidgets.QMessageBox.Yes:
            query = QtSql.QSqlQuery()
            query.exec("DELETE FROM users")
            self.users_model.setTable("users")
            self.users_model.select()

    def version(self):
        QtWidgets.QMessageBox.information(
            None,
            "Wersja  %s" % VERSION_NUMBER,
            "Wersja  %s" % VERSION_NUMBER,
        )

    def deleteCalls(self):
        self._deleteFromTable("current_calls",self.calls_model,QtSql.QSqlQuery(Q1))

    def deleteHistory(self):
        self._deleteFromTable("history_calls",self.history_model,QtSql.QSqlQuery(Q2))

    def settings(self):        
        self.settings_widget.show()

    def filter_voip(self,data):
        if data:
            f = " (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')"
            sql = VOIP_QUERY_FILTER % f
            self.voip_model.setQuery(QtSql.QSqlQuery(sql))
        else:
            self.voip_model.setQuery(QtSql.QSqlQuery(VOIP_QUERY))

        self.history_model.select()

    def filter_history(self,data):
        if data:
            f = " (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')"
            sql = Q2_FILTER % f
            self.history_model.setQuery(QtSql.QSqlQuery(sql))
        else:
            self.history_model.setQuery(QtSql.QSqlQuery(Q2))

        self.history_model.select()

    def filter_calls(self,data):
        if data:
            f = " (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')"
            sql = Q1_FILTER % f
            self.calls_model.setQuery(QtSql.QSqlQuery(sql))
        else:
            self.calls_model.setQuery(QtSql.QSqlQuery(Q1))

        self.calls_model.select()
        
    def filter_users(self,data):
        if data:
            self.users_model.setFilter(" (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')")
        else:
            self.users_model.setFilter("")


class CustomerDialog(QtWidgets.QDialog):
    def __init__(self,message=tuple()):
        super().__init__()
        self.message = message
        self.setWindowTitle("Wysyłka na Slack'a")
        self.createFormGroupBox()
        #QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Ignore

        button = QtWidgets.QPushButton("Slack it !")
        button.clicked.connect(self.slackit)
        
        self.buttonBox = QtWidgets.QDialogButtonBox()
        #self.buttonBox.addButton(QBtn)
        self.buttonBox.addButton(button,QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Zamknij",QtWidgets.QDialogButtonBox.RejectRole)
        #self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QtWidgets.QVBoxLayout()
        #message = QtWidgets.QLabel("Tekst do wysłania:")
        #self.layout.addWidget(message)
        self.layout.addWidget(self.formGroupBox)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def createFormGroupBox(self):
        self.formGroupBox = QtWidgets.QGroupBox("Wysyłka na kanał slackowy. Żeby dodać powiadomienie <@username>")
        layout = QtWidgets.QFormLayout()
        self.textbox = QtWidgets.QPlainTextEdit(self)

        m = (self.message['start_time'],'Tel: '+self.message['calling_number'],self.message['adr_NazwaPelna'],'NIP: '+self.message['adr_NIP'],self.message['adr_Miejscowosc'],self.message['adr_Ulica'])        
        self.textbox.setPlainText("\r\n".join(m))
        
        layout.addRow(QtWidgets.QLabel("Wiadomość:"), self.textbox)
        users = slack.get_members()
        self.cb = QtWidgets.QComboBox()
        self.cb.addItem('')
        slack_users = db.slack_users_list()
        for user in slack_users:
            self.cb.addItem(user[1],user[0])
        layout.addRow(QtWidgets.QLabel("Pobudka:"), self.cb)
        layout.addRow(QtWidgets.QLabel("Kanał:"), QtWidgets.QLabel("#mikran_ogolnie"))
        self.formGroupBox.setLayout(layout)

    def slackit(self):
        message = self.textbox.toPlainText()
        mention = self.cb.itemData(self.cb.currentIndex())
        if mention:
            message = message + "\r\n" + "<@"+mention+">"

        slack.send_message(message.strip())
        QtWidgets.QMessageBox.critical(
            None,
            "Wysłano",
            "Poleciało w kanał",
        )

class MikranTableModel(QtSql.QSqlTableModel):
    def __init__(self, config):
        super(MikranTableModel, self).__init__()
        self.config = config
        self._color = QtCore.Qt.gray

    def data(self, index, role=None):
       v = QtSql.QSqlTableModel.data(self, index, role)

       if role == QtCore.Qt.BackgroundRole:
           if self._color:
               return QtGui.QBrush(self._color)

       if role == Qt.DisplayRole:
         #  self._color = QtCore.Qt.gray
           self._color = None
           if v == 'InCall':
               self._color = QtCore.Qt.green
               return "Odebrane"
           if v == 'OutCall':
               self._color = QtCore.Qt.gray
               return "Wychodzące"
           if v == 'MissedCall':
               self._color = QtCore.Qt.red
               return "Nieodebrane"           
           if v == 'NewCall_ST':
               self._color = QtCore.Qt.yellow
               return "Nowe połączenie"
           if v == 'Connect_ST':
               self._color = QtCore.Qt.green
               login = self.record(index.row()).value("login")
               return "Odebrane u mnie (%s)" % login
           if v == 'call_intercepted':
               self._color = QtCore.Qt.green
               return "Odebrane w grupie"
           if v == config.VOIP_NEW:
               self._color = QtCore.Qt.yellow
               return "Nieokreślone"
           if v == config.VOIP_ANSWERED:
               self._color = QtCore.Qt.green
               return "Odebrane"
               
           try:
               dt = datetime.datetime.strptime(v,"%m-%d-%Y, %H:%M:%S")
               v = dt.strftime("%A, %m-%d-%Y, %H:%M:%S")
           except Exception as e:
               pass

           try:
               dt = datetime.datetime.strptime(v,"%Y-%m-%d %H:%M:%S")
               v = dt.strftime("%A, %m-%d-%Y, %H:%M:%S")
           except Exception as e:
               pass
           
       return v

       
class CallsTableView(QtWidgets.QTableView):
    def __init__(self,current_calls_columns,parent=None):
        self.current_calls_columns = current_calls_columns
        super(CallsTableView,self).__init__(parent)
        
    def mouseDoubleClickEvent(self, event):
        current_row = self.currentIndex().row()
        selected = []
        
        for i in range(self.model().columnCount()):
            col = self.current_calls_columns[i]
            index = self.model().index(current_row,i)
            selected.append((col,self.model().data(index,Qt.ItemDataRole.DisplayRole)))

        dlg = CustomerDialog(dict(selected))
        dlg.exec()
            
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Enter:
            print("ENTER")
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_Backspace:
            #self.model().removeRow(self.currentIndex().row())
            QtWidgets.QMessageBox.critical(
                None,
                "Delete",
                "Usunięto rekord na pozycji %d" % self.currentIndex().row(),
            )
        super(CallsTableView, self).keyPressEvent(event)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
