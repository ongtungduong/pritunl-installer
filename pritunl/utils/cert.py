from pritunl.constants import *
from pritunl.utils.misc import check_output_logged, get_temp_path
from pritunl import settings

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

import os
import uuid

def create_server_cert():
    from pritunl import acme

    if settings.app.acme_domain:
        acme.update_acme_cert()
        return

    server_cert, server_key = generate_server_cert()
    settings.app.server_cert = server_cert
    settings.app.server_key = server_key

def generate_server_cert():
    server_cert_path = os.path.join(settings.conf.temp_path, SERVER_CERT_NAME)
    server_key_path = os.path.join(settings.conf.temp_path, SERVER_KEY_NAME)

    check_output_logged([
        'openssl', 'ecparam', '-name', 'secp384r1', '-genkey', '-noout',
        '-out', server_key_path,
    ])
    check_output_logged([
        'openssl', 'req', '-new', '-batch', '-x509', '-days', '3652',
        '-key', server_key_path,
        '-out', server_cert_path,
    ])
    os.chmod(server_key_path, 0o600)

    with open(server_cert_path, 'r') as server_cert_file:
        server_cert = server_cert_file.read().strip()
    with open(server_key_path, 'r') as server_key_file:
        server_key = server_key_file.read().strip()

    os.remove(server_cert_path)
    os.remove(server_key_path)

    return server_cert, server_key

def generate_private_key():
    return check_output_logged([
        'openssl', 'genrsa', '4096',
    ])

def generate_private_ec_key():
    return check_output_logged([
        'openssl', 'ecparam', '-name', 'secp384r1', '-genkey', '-noout',
    ])

def generate_csr(private_key, domain, cmdline=False):
    if cmdline:
        private_key_path = '/tmp/pritunl_' + uuid.uuid4().hex + '.key'
    else:
        private_key_path = get_temp_path() + '.key'

    with open(private_key_path, 'w') as private_key_file:
        os.chmod(private_key_path, 0o600)
        private_key_file.write(private_key)

    csr = check_output_logged([
        'openssl',
        'req',
        '-new',
        '-batch',
        '-sha256',
        '-key', private_key_path,
        '-subj', '/CN=%s' % domain,
    ])

    try:
        os.remove(private_key_path)
    except:
        pass

    return csr

def generate_rsa_key():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem.decode().strip(), public_pem.decode().strip()
