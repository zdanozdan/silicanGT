#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5 import QtSql

#XML
import xml.etree.ElementTree as ET
#Thread
from sync import CallHistoryThread
#sqlite
import sqlite3
from datetime import datetime

import db,gt,config,silican

class Window(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.setWindowTitle("mikran.pl - integracja centrali telefonicznej")
        self.setWindowIcon(QIcon('yoda.png')) 
        self.resize(800, 600)
        self.statusBar().showMessage('mikran.pl. Ready')
        db.init_db()
        self.config = db.load_config()
        con = db.create_con()
        if not con.open():
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

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(vbox)
        self.setCentralWidget(self.widget)
        
        #self.createToolBar()
        self.createMenuBar()
        self.createSettingsWigdet()
        self.start_threads()

    def createMenuBar(self):
        usersAction = QtWidgets.QAction(QIcon('download.png'), '&Pobierz kontrahentów', self)
        usersAction.setShortcut('Ctrl+P')
        usersAction.setStatusTip('Pobierz konkrahentów z baz danych')
        usersAction.triggered.connect(self.usersActionThread)

        settingsAction = QtWidgets.QAction(QIcon('settings.png'), '&Ustawienia', self)
        settingsAction.setShortcut('Ctrl+U')
        settingsAction.setStatusTip('UStawienia')
        settingsAction.triggered.connect(self.settings)
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&Plik')
        fileMenu.addAction(usersAction)
        fileMenu.addAction(settingsAction)

    def usersActionThread(self):
        gt_thread = gt.GTThread(parent=self)
        gt_thread._signal.connect(self.signal_gt)
        gt_thread.start()
        self.statusBar().setStyleSheet("color: green")
        self.statusBar().showMessage('Pobieranie listy kontrahentów ....')        

    def start_threads(self):
        silican_thread = silican.SilicanConnectionThread(parent=self)
        silican_thread._signal.connect(self.signal_silican)
        silican_thread.start()

    def signal_silican(self,data):
        if data[0] == config.SILICAN_CONNECTED:
            self.statusBar().showMessage('Centrala podłączona')
        if data[0] == config.SILICAN_ERROR:
            self.statusBar().showMessage('Nie udało się podłączyć do centrali')
            QtWidgets.QMessageBox.critical(
                None,
                "Błąd podczas łączenia do centrali %s" % data[1],
                "Błąd podczas łączenia do centrali %s" % data[1],
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

    def addModels(self):
        self.users_model = MikranTableModel(self)
        self.users_model.setTable("users")
        self.users_model.select()

        self.calls_model = QtSql.QSqlRelationalTableModel(self)
        self.calls_model.setQuery(QtSql.QSqlQuery("select * from current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer"))
        self.calls_model.select()

    def addViews(self):
        self.tableview_users = QtWidgets.QTableView()
        self.tableview_users.setModel(self.users_model)
        self.tableview_users.resizeColumnsToContents()
        self.tableview_users.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_users.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_users.setSortingEnabled(True)
        self.tableview_users.setWordWrap(True);
        self.tableview_users.update()

        self.tableview_calls = QtWidgets.QTableView()
        self.tableview_calls.setModel(self.calls_model)
        self.tableview_calls.resizeColumnsToContents()
        self.tableview_calls.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_calls.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_calls.setSortingEnabled(True)
        self.tableview_calls.setWordWrap(True);
        self.tableview_calls.update()

    def addTabs(self,vbox):
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tab3 = QtWidgets.QWidget()
        self.tabs.addTab(self.tab1,"Bieżące połączenia")
        self.tabs.addTab(self.tab2,"Historyczne")
        self.tabs.addTab(self.tab3,"Kontakty")
        vbox.addWidget(self.tabs)

        layout = QtWidgets.QVBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.textChanged.connect(self.filter_users)
        layout.addWidget(line_edit)
        layout.addWidget(self.tableview_users)
        self.tab3.setLayout(layout)

        layout_calls = QtWidgets.QVBoxLayout()
        line_edit_calls = QtWidgets.QLineEdit()
        #line_edit.textChanged.connect(self.filter_users)
        layout_calls.addWidget(line_edit_calls)
        layout_calls.addWidget(self.tableview_calls)
        self.tab1.setLayout(layout_calls)
        
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

    def settings(self):        
        self.settings_widget.show()

    def filter_users(self,data):
        if data:
            self.users_model.setFilter(" (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')")
        else:
            self.users_model.setFilter("")        

class MikranTableModel(QtSql.QSqlTableModel):
   def __init__(self, dbcursor=None):
       super(MikranTableModel, self).__init__()
       #self._color = QtCore.Qt.gray


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
