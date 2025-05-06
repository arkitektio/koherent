from django.apps import AppConfig


class TestingModuleConfig(AppConfig):
    """ Django AppConfig for the testing module. """
    default_auto_field = "django.db.models.BigAutoField"
    name = "testing_module"
