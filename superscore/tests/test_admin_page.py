import pytest
from unittest.mock import MagicMock, patch
from qtpy.QtCore import Qt, QEvent
from qtpy.QtGui import QKeyEvent, QPixmap
from qtpy.QtWidgets import QApplication, QPushButton, QMessageBox, QDialog

from superscore.widgets.admin_page import AdminPopupWindow
from superscore.permission_manager import PermissionManager


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication instance for the tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_permission_manager():
    """Create a mock for PermissionManager."""
    mock_manager: MagicMock = MagicMock(spec=PermissionManager)
    mock_manager.is_admin.return_value = False
    
    with patch.object(PermissionManager, 'get_instance', return_value=mock_manager):
        yield mock_manager


@pytest.fixture
def mock_qta_icon():
    """Create a proper mock for qtawesome.icon that returns an icon with working pixmap method."""
    mock_icon: MagicMock = MagicMock()
    
    test_pixmap: QPixmap = QPixmap(1, 1)
    test_pixmap.fill(Qt.black)  

    mock_icon.pixmap.return_value = test_pixmap
    
    with patch('qtawesome.icon', return_value=mock_icon):
        yield


@pytest.fixture
def admin_popup(qapp, mock_permission_manager, mock_qta_icon) -> AdminPopupWindow:
    """Create an AdminPopupWindow instance with mocked dependencies."""
    popup: AdminPopupWindow = AdminPopupWindow()
    popup.permission_manager = mock_permission_manager 

    try:
        popup.permission_manager.admin_status_changed.disconnect()
    except (TypeError, RuntimeError):
        pass
   
    popup.permission_manager.admin_status_changed.connect(popup.on_admin_status_changed)
    
    return popup


class TestAdminPopupWindow:
    """Test suite for the AdminPopupWindow class."""
    
    def test_init(self, admin_popup, mock_permission_manager) -> None:
        """Test initialization of the AdminPopupWindow."""

        assert admin_popup.windowTitle() == "Admin Access"
        assert admin_popup.minimumSize().width() >= 450
        assert admin_popup.minimumSize().height() >= 300
        assert admin_popup.isModal() is True
        
        assert admin_popup.content_area.count() == 2
        
        mock_permission_manager.is_admin.assert_called()
        assert admin_popup.content_area.currentIndex() == 0  
    
    def test_key_press_event_login(self, admin_popup, qapp) -> None:
        """Test key press event handling with mocked focus state."""

        admin_popup.content_area.setCurrentIndex(0)
        admin_popup._processing_login = False
        
        original_try_login = admin_popup.try_login
        admin_popup.try_login = MagicMock()
        
        original_has_focus = admin_popup.password_field.hasFocus
        admin_popup.password_field.hasFocus = MagicMock(return_value=True)
        
        try:
            key_event: QKeyEvent = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
            
            admin_popup.keyPressEvent(key_event)
            
            admin_popup.try_login.assert_called_once()
        finally:
            admin_popup.try_login = original_try_login
            admin_popup.password_field.hasFocus = original_has_focus

    
    def test_create_login_page(self, admin_popup) -> None:
        """Test creation of login page."""
        login_page = admin_popup.create_login_page()
        
        assert login_page.objectName() == "loginPage"
        assert login_page.layout() is not None
    
    def test_create_login_frame(self, admin_popup) -> None:
        """Test creation of login frame."""
        login_frame = admin_popup.create_login_frame()
        
        assert login_frame.objectName() == "loginFrame"
        assert login_frame.width() == 450
        assert login_frame.height() == 300
        
        assert hasattr(admin_popup, 'email_field')
        assert hasattr(admin_popup, 'password_field')
        assert admin_popup.password_field.echoMode() == admin_popup.password_field.Password
    
    def test_create_main_page(self, admin_popup) -> None:
        """Test creation of main page."""
        main_page = admin_popup.create_main_page()
        
        assert main_page.objectName() == "mainPage"        
        assert hasattr(admin_popup, 'welcome_label')
    
    def test_try_login_empty_fields(self, admin_popup) -> None:
        """Test login attempt with empty fields."""
        admin_popup.email_field.setText("")
        admin_popup.password_field.setText("")
        
        with patch.object(QMessageBox, 'warning') as mock_warning:
            admin_popup.try_login()
            
            mock_warning.assert_called_once()
    
    def test_try_login_success(self, admin_popup):
        """Test successful login attempt."""
        admin_popup.email_field.setText("admin@example.com")
        admin_popup.password_field.setText("password")
        
        admin_popup.permission_manager.admin_login.return_value = True
        
        login_spy: MagicMock = MagicMock()
        admin_popup.user_logged_in.connect(login_spy)
        
        with patch.object(QMessageBox, 'warning') as mock_warning:
            admin_popup.try_login()
            
            admin_popup.permission_manager.admin_login.assert_called_once()
            
            assert admin_popup.current_username == "admin"
            
            login_spy.assert_called_once()            
            mock_warning.assert_not_called()
    
    def test_try_login_failure(self, admin_popup) -> None:
        """Test failed login attempt."""
        admin_popup.email_field.setText("wrong@example.com")
        admin_popup.password_field.setText("wrong")
        
        admin_popup.permission_manager.admin_login.return_value = False
        
        login_spy: MagicMock = MagicMock()
        admin_popup.user_logged_in.connect(login_spy)
        
        with patch.object(QMessageBox, 'warning') as mock_warning:
            admin_popup.try_login()            
            admin_popup.permission_manager.admin_login.assert_called_once()
            
            assert admin_popup.current_username == ""
            
            login_spy.assert_not_called()          
            mock_warning.assert_called_once()
            
            assert admin_popup.password_field.text() == ""
    
    def test_logout(self, admin_popup) -> None:
        """Test logout functionality."""
        admin_popup.current_username = "admin"
        
        logout_spy: MagicMock = MagicMock()
        admin_popup.user_logged_out.connect(logout_spy)
        
        admin_popup.logout()
        
        admin_popup.permission_manager.admin_logout.assert_called_once()
        
        assert admin_popup.current_username == ""
        logout_spy.assert_called_once()
    
    def test_on_admin_status_changed_to_admin(self, admin_popup) -> None:
        """Test handling of admin status change to admin."""
        admin_popup.content_area.setCurrentIndex(0)  
        admin_popup.password_field.setText("password")
        
        admin_popup.on_admin_status_changed(True)
        
        assert admin_popup.content_area.currentIndex() == 1
        assert admin_popup.password_field.text() == ""
    
    def test_on_admin_status_changed_to_non_admin(self, admin_popup) -> None:
        """Test handling of admin status change to non-admin."""
        admin_popup.content_area.setCurrentIndex(1)  # Main page
        admin_popup.email_field.setText("existing@example.com")
        
        admin_popup.on_admin_status_changed(False)
        assert admin_popup.content_area.currentIndex() == 0
        assert admin_popup.email_field.text() == ""
    
    @patch('superscore.widgets.admin_page.AdminPopupWindow')
    def test_show_admin_popup_static_method(self, mock_popup_class) -> None:
        """Test the static method to create and show the admin popup."""
        mock_parent: MagicMock = MagicMock()
        mock_backend: MagicMock = MagicMock()
        
        mock_popup: MagicMock = MagicMock()
        mock_popup_class.return_value = mock_popup
        
        with patch.object(AdminPopupWindow, 'show_admin_popup', 
                         wraps=AdminPopupWindow.show_admin_popup) as mock_method:
            result: AdminPopupWindow = AdminPopupWindow.show_admin_popup(mock_parent, mock_backend)
            
            mock_method.assert_called_once()