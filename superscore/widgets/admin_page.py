import qtawesome as qta
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                            QMessageBox, QPushButton, QStackedWidget,
                            QVBoxLayout, QWidget)

from superscore.permission_manager import PermissionManager


class AdminPopupWindow(QDialog):
    """
    Admin authentication popup window that handles login credentials and permissions.

    This class provides a popup dialog for admin authentication, with login and
    dashboard views. It uses a PermissionManager to validate access credentials
    and manage admin status.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget, by default None
    backend_api : object, optional
        Backend API for authentication, by default None

    Attributes
    ----------
    user_logged_in : Signal
        Signal emitted when a user successfully logs in, passes username
    user_logged_out : Signal
        Signal emitted when a user logs out
    """

    user_logged_in = Signal(str)  # Emits username on successful login
    user_logged_out = Signal()    # Emits when user logs out

    def __init__(self, parent=None, backend_api=None) -> None:
        """
        Initialize the admin popup window.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget, by default None
        backend_api : object, optional
            Backend API for authentication, by default None
        """
        super().__init__(parent)

        self.setWindowTitle("Admin Access")
        self.setMinimumSize(450, 300)
        self.setModal(True)

        self.backend_api = backend_api
        self.current_username = ""

        self.permission_manager = PermissionManager.get_instance()
        self.permission_manager.admin_status_changed.connect(self.on_admin_status_changed)

        main_layout: QVBoxLayout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.content_area = QStackedWidget()
        self.content_area.setObjectName("contentArea")

        login_page: QWidget = self.create_login_page()
        self.content_area.addWidget(login_page)

        main_page: QWidget = self.create_main_page()
        self.content_area.addWidget(main_page)

        is_admin = self.permission_manager.is_admin()
        self.content_area.setCurrentIndex(1 if is_admin else 0)

        main_layout.addWidget(self.content_area)

        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event) -> None:
        """
        Override keyPressEvent to handle Enter key properly.

        This method intercepts Enter/Return key presses and triggers the login action
        when appropriate, with safeguards to prevent duplicate processing.

        Parameters
        ----------
        event : QKeyEvent
            The key event to handle
        """
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.content_area.currentIndex() == 0 and self.password_field.hasFocus():
                event.accept()
                if not hasattr(self, '_processing_login') or not self._processing_login:
                    self._processing_login = True
                    self.try_login()
                    self._processing_login = False
                return
            elif self.content_area.currentIndex() == 1:
                event.accept()
                return
        super().keyPressEvent(event)

    def create_login_page(self) -> QWidget:
        """
        Create the login page with login frame.

        Returns
        -------
        QWidget
            The login page widget containing the login frame
        """
        login_page: QWidget = QWidget()
        login_page.setObjectName("loginPage")

        layout: QVBoxLayout = QVBoxLayout(login_page)
        layout.setContentsMargins(0, 0, 0, 0)

        login_frame: QFrame = self.create_login_frame()
        layout.addWidget(login_frame, 0, Qt.AlignCenter)

        return login_page

    def create_login_frame(self) -> QFrame:
        """
        Create the login form frame with input fields and buttons.

        Returns
        -------
        QFrame
            The styled frame containing the login form elements
        """
        login_frame: QFrame = QFrame()
        login_frame.setObjectName("loginFrame")
        login_frame.setFixedSize(450, 300)
        login_frame.setFrameShape(QFrame.StyledPanel)

        layout: QVBoxLayout = QVBoxLayout(login_frame)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        header_layout: QHBoxLayout = QHBoxLayout()
        header_layout.setSpacing(10)

        icon_label: QLabel = QLabel()
        icon_pixmap: QPixmap = qta.icon("msc.squirrel", color='#555555').pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)

        title: QLabel = QLabel("<b>Squirrel</b><br><big>Admin Log-In</big><br>Please enter your details")
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

        login_button: QPushButton = QPushButton("Log in")
        login_button.setObjectName("loginButton")
        login_button.clicked.connect(self.try_login)

        cancel_button: QPushButton = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.clicked.connect(self.reject)

        button_layout: QHBoxLayout = QHBoxLayout()
        button_layout.addWidget(login_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(header_layout)
        layout.addSpacing(10)
        layout.addWidget(self.email_field)
        layout.addWidget(self.password_field)
        layout.addSpacing(20)
        layout.addLayout(button_layout)

        self._processing_login = False
        self.email_field.returnPressed.connect(self.password_field.setFocus)

        return login_frame

    def create_main_page(self) -> QWidget:
        """
        Create the main application page shown after successful login.

        Returns
        -------
        QWidget
            The admin dashboard widget with welcome message and action buttons
        """
        main_page: QWidget = QWidget()
        main_page.setObjectName("mainPage")

        layout: QVBoxLayout = QVBoxLayout(main_page)
        layout.setContentsMargins(30, 30, 30, 30)

        self.welcome_label = QLabel("Welcome to Admin Dashboard")
        self.welcome_label.setObjectName("welcomeLabel")
        self.welcome_label.setAlignment(Qt.AlignCenter)

        logout_button: QPushButton = QPushButton("Logout")
        logout_button.setObjectName("logoutButton")
        logout_button.clicked.connect(self.logout)

        close_button: QPushButton = QPushButton("Close")
        close_button.setObjectName("closeButton")
        close_button.clicked.connect(self.accept)

        button_layout: QHBoxLayout = QHBoxLayout()
        button_layout.addWidget(logout_button)
        button_layout.addWidget(close_button)

        layout.addWidget(self.welcome_label)
        layout.addSpacing(20)
        layout.addLayout(button_layout)
        layout.addStretch(1)

        return main_page

    def try_login(self) -> None:
        """
        Process login attempt using PermissionManager.

        Validates the email and password inputs and attempts to authenticate
        the user. Updates the UI based on authentication result.
        """
        email: str = self.email_field.text()
        password: str = self.password_field.text()

        if not email or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both email and password")
            return

        if self.permission_manager.admin_login(email, password, self.backend_api):
            self.current_username = email.split('@')[0] if '@' in email else email
            self.welcome_label.setText(f"Welcome, {self.current_username}")
            self.user_logged_in.emit(self.current_username)
            try:
                self.password_field.returnPressed.disconnect(self.try_login)
            except TypeError:
                pass
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid email or password")
            self.password_field.clear()
            self.password_field.setFocus()

    def logout(self) -> None:
        """
        Log out the current user using PermissionManager.

        Clears the current username and emits the user_logged_out signal.
        """
        self.permission_manager.admin_logout()
        self.current_username = ""
        self.user_logged_out.emit()

    def on_admin_status_changed(self, is_admin) -> None:
        """
        Handle admin status changes from PermissionManager.

        Updates the UI based on the current admin status, switching between
        login and dashboard views.

        Parameters
        ----------
        is_admin : bool
            Flag indicating whether the user has admin status
        """
        if is_admin:
            self.content_area.setCurrentIndex(1)
            self.password_field.clear()
        else:
            self.content_area.setCurrentIndex(0)
            self.email_field.clear()
            self.email_field.setFocus()
            try:
                self.password_field.returnPressed.connect(self.try_login)
            except TypeError:
                pass

    @staticmethod
    def show_admin_popup(parent=None, backend_api=None) -> 'AdminPopupWindow':
        """
        Static method to create and show the admin popup.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget, by default None
        backend_api : object, optional
            Backend API for authentication, by default None

        Returns
        -------
        AdminPopupWindow
            The created dialog instance
        """
        dialog: AdminPopupWindow = AdminPopupWindow(parent, backend_api)
        return dialog
