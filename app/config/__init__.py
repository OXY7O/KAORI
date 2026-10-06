from app.config.default import Config
from app.config.development import DevelopmentConfig
from app.config.production import ProductionConfig
from app.config.testing import TestingConfig

# Map of configuration names to classes
CONFIG_MAP = {
    'default': Config,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}
