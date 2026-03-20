"""Generate self-signed SSL certificate for local HTTPS development.
Run: python scripts/gen_ssl_cert.py
Then: uvicorn app.main:app --reload --ssl-keyfile=.dev/key.pem --ssl-certfile=.dev/cert.pem
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Install: pip install cryptography")
    raise SystemExit(1)

def main():
    dev_dir = Path(__file__).resolve().parent.parent / ".dev"
    dev_dir.mkdir(exist_ok=True)
    key_file = dev_dir / "key.pem"
    cert_file = dev_dir / "cert.pem"
    if key_file.exists() and cert_file.exists():
        print(f"Cert exists: {cert_file}")
        return

    key = rsa.generate_private_key(65537, 2048, default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.DNSName("127.0.0.1")]),
            critical=False,
        )
        .sign(key, hashes.SHA256(), default_backend())
    )
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Created: {key_file}, {cert_file}")
    print("Run: uvicorn app.main:app --reload --ssl-keyfile=.dev/key.pem --ssl-certfile=.dev/cert.pem")

if __name__ == "__main__":
    main()
