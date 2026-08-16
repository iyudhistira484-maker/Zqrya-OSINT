"""Zqrya v3.0 modules package"""
from modules.username import UsernameModule
from modules.email import EmailModule
from modules.phone import PhoneModule
from modules.domain import DomainModule
from modules.ip import IPModule
from modules.url import URLModule
from modules.maigret import MaigretModule
from modules.darkweb import DarkWebModule

__all__ = [
    'UsernameModule',
    'EmailModule',
    'PhoneModule',
    'DomainModule',
    'IPModule',
    'URLModule',
    'MaigretModule',
    'DarkWebModule'
]
