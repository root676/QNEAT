# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'qneat_dockwidget_base.ui'
#
# Created: Sun Jul 09 18:06:01 2017
#      by: PyQt4 UI code generator 4.10.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_QNEATDockWidgetBase(object):
    def setupUi(self, QNEATDockWidgetBase):
        QNEATDockWidgetBase.setObjectName(_fromUtf8("QNEATDockWidgetBase"))
        QNEATDockWidgetBase.resize(232, 141)
        self.dockWidgetContents = QtGui.QWidget()
        self.dockWidgetContents.setObjectName(_fromUtf8("dockWidgetContents"))
        self.gridLayout = QtGui.QGridLayout(self.dockWidgetContents)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.label = QtGui.QLabel(self.dockWidgetContents)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        QNEATDockWidgetBase.setWidget(self.dockWidgetContents)

        self.retranslateUi(QNEATDockWidgetBase)
        QtCore.QMetaObject.connectSlotsByName(QNEATDockWidgetBase)

    def retranslateUi(self, QNEATDockWidgetBase):
        QNEATDockWidgetBase.setWindowTitle(_translate("QNEATDockWidgetBase", "QNEAT", None))
        self.label.setText(_translate("QNEATDockWidgetBase", "QNEAT", None))

