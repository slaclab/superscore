from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                           QMessageBox, QPushButton, QStackedWidget,
                           QVBoxLayout, QWidget)
import qtawesome as qta

from superscore.permission_manager import PermissionManager


class AdminPopupWindow(QDialog):
    # Define signals for login and logout events
    user_logged_in = Signal(str)  # Emits username on successful login
    user_logged_out = Signal()    # Emits when user logs out
    
    def __init__(self, parent=None, backend_api=None):
        super().__init__(parent)
        
        self.setWindowTitle("Admin Access")
        self.setMinimumSize(450, 300)
        self.setModal(True)
        
        self.backend_api = backend_api
        self.current_username = ""

        self.permission_manager = PermissionManager.get_instance()
        self.permission_manager.admin_status_changed.connect(self.on_admin_status_changed)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.content_area = QStackedWidget()
        self.content_area.setObjectName("contentArea")

        login_page = self.create_login_page()
        self.content_area.addWidget(login_page)

        main_page = self.create_main_page()
        self.content_area.addWidget(main_page)

        # Set initial page based on current admin status
        is_admin = self.permission_manager.is_admin()
        self.content_area.setCurrentIndex(1 if is_admin else 0)

        main_layout.addWidget(self.content_area)

    def create_login_page(self):
        """Create the login page with login frame"""
        login_page = QWidget()
        login_page.setObjectName("loginPage")

        layout = QVBoxLayout(login_page)
        layout.setContentsMargins(0, 0, 0, 0)

        login_frame = self.create_login_frame()
        layout.addWidget(login_frame, 0, Qt.AlignCenter)

        return login_page

    def create_login_frame(self):
        """Create the login form frame"""
        login_frame = QFrame()
        login_frame.setObjectName("loginFrame")
        login_frame.setFixedSize(450, 300)
        login_frame.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(login_frame)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        icon_label = QLabel()
        icon_pixmap = qta.icon("msc.squirrel", color='#555555').pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)

        title = QLabel("<b>Squirrel</b><br><big>Admin Log-In</big><br>Please enter your details")
        title.setObjectName("loginTitle")

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.email_field = QLineEdit()
        self.email_field.setPlaceholderText("Email")
        self.email_field.setObjectName("emailField")

        self.password_field = QLineEdit()
        self.password_field.setPlaceholderText("Password")
        self.password_field.setEchoMode(QLineEdit.Password)
        self.password_field.setObjectName("passwordField")

        login_button = QPushButton("Log in")
        login_button.setObjectName("loginButton")
        login_button.clicked.connect(self.try_login)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.clicked.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(login_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(header_layout)
        layout.addSpacing(10)
        layout.addWidget(self.email_field)
        layout.addWidget(self.password_field)
        layout.addSpacing(20)
        layout.addLayout(button_layout)

        self.email_field.returnPressed.connect(self.password_field.setFocus)
        self.password_field.returnPressed.connect(self.try_login)

        return login_frame

    def create_main_page(self):
        """Create the main application page (shown after login)"""
        main_page = QWidget()
        main_page.setObjectName("mainPage")

        layout = QVBoxLayout(main_page)
        layout.setContentsMargins(30, 30, 30, 30)

        self.welcome_label = QLabel("Welcome to Admin Dashboard")
        self.welcome_label.setObjectName("welcomeLabel")
        self.welcome_label.setAlignment(Qt.AlignCenter)

        logout_button = QPushButton("Logout")
        logout_button.setObjectName("logoutButton")
        logout_button.clicked.connect(self.logout)
        
        close_button = QPushButton("Close")
        close_button.setObjectName("closeButton")
        close_button.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(logout_button)
        button_layout.addWidget(close_button)

        layout.addWidget(self.welcome_label)
        layout.addSpacing(20)
        layout.addLayout(button_layout)
        layout.addStretch(1)

        return main_page

    def try_login(self):
        """Process login attempt using PermissionManager"""
        email = self.email_field.text()
        password = self.password_field.text()

        if not email or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both email and password")
            return

        if self.permission_manager.admin_login(email, password, self.backend_api):
            # Extract username from email (everything before @)
            self.current_username = email.split('@')[0] if '@' in email else email
            # Update welcome message
            self.welcome_label.setText(f"Welcome, {self.current_username}")
            # Emit signal with username
            self.user_logged_in.emit(self.current_username)
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid email or password")
            self.password_field.clear()
            self.password_field.setFocus()

    def logout(self):
        """Log out using PermissionManager"""
        self.permission_manager.admin_logout()
        self.current_username = ""
        self.user_logged_out.emit()
        
    def on_admin_status_changed(self, is_admin):
        """Handle admin status changes"""
        if is_admin:
            self.content_area.setCurrentIndex(1)
            self.password_field.clear()
        else:
            self.content_area.setCurrentIndex(0)
            self.email_field.clear()
            self.email_field.setFocus()
    
    @staticmethod
    def show_admin_popup(parent=None, backend_api=None):
        """Static method to create and show the admin popup"""
        dialog = AdminPopupWindow(parent, backend_api)
        return dialog
