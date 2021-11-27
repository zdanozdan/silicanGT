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

import db,gt,config

class Window(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.setWindowTitle("mikran.pl - integracja centrali telefonicznej")
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
        vbox.addWidget(QtWidgets.QLabel("LABEL"))
        self.addTabs(vbox)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(vbox)
        self.setCentralWidget(self.widget)
        
        self.createToolBar()        
        self.createSettingsWigdet()
        self.start_threads()

    def start_threads(self):
        gt_thread = gt.GTThread(parent=self)
        gt_thread._signal.connect(self.signal_gt)
        gt_thread.start()

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

    def addViews(self):
        self.tableview_users = QtWidgets.QTableView()
        self.tableview_users.setModel(self.users_model)
        self.tableview_users.resizeColumnsToContents()
        self.tableview_users.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_users.sortByColumn(1, Qt.DescendingOrder);
        self.tableview_users.setSortingEnabled(True)
        self.tableview_users.setWordWrap(True);
        self.tableview_users.update()

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
        self.tab1.setLayout(layout)
        
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
            self.users_model.setFilter(" (adr_Telefon like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')")
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
