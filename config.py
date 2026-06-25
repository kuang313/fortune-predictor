import os

class Config:
    GLM_API_KEY = os.environ.get('GLM_API_KEY', '')
    GLM_MODEL = os.environ.get('GLM_MODEL', 'glm-4-flash')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')