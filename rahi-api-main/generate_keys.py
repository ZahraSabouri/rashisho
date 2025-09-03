#!/usr/bin/env python3
"""
Generate RSA key pairs for Rahisho development
Run this script from the project root directory
"""

import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_key_pair(private_path, public_path):
    """Generate RSA private and public key pair"""
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(private_path), exist_ok=True)
    os.makedirs(os.path.dirname(public_path), exist_ok=True)
    
    # Write private key
    with open(private_path, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Write public key
    with open(public_path, 'wb') as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    
    print(f"Generated key pair:")
    print(f"  Private: {private_path}")
    print(f"  Public:  {public_path}")

if __name__ == "__main__":
    # Create test keys directory
    os.makedirs("keys/test", exist_ok=True)
    
    # Generate production keys (optional)
    print("Generating production keys...")
    generate_key_pair("keys/private_key.pem", "keys/public_key.pem")
    
    # Generate test keys
    print("\nGenerating test keys...")
    generate_key_pair("keys/test/private_key.pem", "keys/test/public_key.pem")
    
    print("\n✅ All keys generated successfully!")
    print("\nNext steps:")
    print("1. Set IS_TEST=true in your .env file")
    print("2. Run your Django server")
    print("3. Use /api/v1/account/dev-token/ to get test tokens")