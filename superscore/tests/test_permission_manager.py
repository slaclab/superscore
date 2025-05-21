from unittest.mock import MagicMock

import pytest

from superscore.permission_manager import PermissionManager


class TestPermissionManager:

    def setup_method(self) -> None:
        """Reset the singleton before each test"""
        PermissionManager._instance = None

    def test_get_instance(self) -> None:
        """Test that get_instance returns a singleton instance"""
        instance1 = PermissionManager.get_instance()
        instance2 = PermissionManager.get_instance()

        assert instance1 is instance2
        assert isinstance(instance1, PermissionManager)

    def test_init_singleton_enforcement(self) -> None:
        """Test that direct instantiation raises an exception after singleton is created"""
        PermissionManager.get_instance()

        with pytest.raises(Exception) as excinfo:
            PermissionManager()

        assert "This class is a singleton" in str(excinfo.value)

    def test_admin_login_with_correct_credentials(self) -> None:
        """Test admin login with correct credentials"""
        manager = PermissionManager.get_instance()

        signal_received = False
        signal_value = None

        def on_admin_status_changed(value) -> None:
            nonlocal signal_received, signal_value
            signal_received = True
            signal_value = value

        manager.admin_status_changed.connect(on_admin_status_changed)

        result = manager.admin_login("admin@example.com", "password")

        assert result is True
        assert manager.is_admin() is True
        assert manager.get_admin_token() == "dummy_token"
        assert signal_received is True
        assert signal_value is True

        manager.admin_status_changed.disconnect(on_admin_status_changed)

    def test_admin_login_with_incorrect_credentials(self) -> None:
        """Test admin login with incorrect credentials"""
        manager = PermissionManager.get_instance()

        signal_received = False

        def on_admin_status_changed(value) -> None:
            nonlocal signal_received
            signal_received = True

        manager.admin_status_changed.connect(on_admin_status_changed)

        result = manager.admin_login("wrong@example.com", "wrong_password")

        assert result is False
        assert manager.is_admin() is False
        assert manager.get_admin_token() is None
        assert signal_received is False

        manager.admin_status_changed.disconnect(on_admin_status_changed)

    def test_admin_login_with_backend_api(self) -> None:
        """Test admin login with backend API"""
        manager = PermissionManager.get_instance()

        mock_api: MagicMock = MagicMock()
        mock_api.admin_login.return_value = {"success": True, "token": "api_token"}

        signal_received = False

        def on_admin_status_changed(value) -> None:
            nonlocal signal_received
            signal_received = True

        manager.admin_status_changed.connect(on_admin_status_changed)

        result = manager.admin_login("admin@example.com", "password", backend_api=mock_api)

        assert result is True
        assert manager.is_admin() is True
        assert manager.get_admin_token() == "api_token"
        assert signal_received is True
        mock_api.admin_login.assert_called_once_with("admin@example.com", "password")

        manager.admin_status_changed.disconnect(on_admin_status_changed)

    def test_admin_logout(self) -> None:
        """Test admin logout"""
        manager = PermissionManager.get_instance()

        manager.admin_login("admin@example.com", "password")

        signal_received = False
        signal_value = None

        def on_admin_status_changed(value) -> None:
            nonlocal signal_received, signal_value
            signal_received = True
            signal_value = value

        manager.admin_status_changed.connect(on_admin_status_changed)

        manager.admin_logout()

        assert manager.is_admin() is False
        assert manager.get_admin_token() is None
        assert signal_received is True
        assert signal_value is False

        manager.admin_status_changed.disconnect(on_admin_status_changed)

    def test_is_admin(self) -> None:
        """Test is_admin method"""
        manager = PermissionManager.get_instance()

        assert manager.is_admin() is False

        manager.admin_login("admin@example.com", "password")
        assert manager.is_admin() is True

        manager.admin_logout()
        assert manager.is_admin() is False

    def test_get_admin_token(self) -> None:
        """Test get_admin_token method"""
        manager = PermissionManager.get_instance()

        assert manager.get_admin_token() is None

        manager.admin_login("admin@example.com", "password")
        assert manager.get_admin_token() == "dummy_token"

        manager.admin_logout()
        assert manager.get_admin_token() is None
