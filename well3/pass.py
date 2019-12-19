import boto3
from base64 import b64decode

with open('encrypted_controls.pem', 'r') as encrypted_pem:
    pem_file = encrypted_pem.read()

print(pem_file)
kms = boto3.client('kms', region_name='us-west-2')
print(kms.decrypt(CiphertextBlob=b64decode(pem_file))['Plaintext'].decode("utf-8"))
