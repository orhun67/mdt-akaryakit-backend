
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, messaging

def initialize_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

    if not secret:
        raise RuntimeError("Firebase servis anahtari bulunamadi.")

    service_account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def check_fuel_data(db):
    print("MDT Akaryakit Takip - Firebase baglantisi")

    for fuel_id in ["motorin", "benzin", "lpg"]:
        doc = db.collection("fuel_status").document(fuel_id).get()

        if doc.exists:
            data = doc.to_dict()
            print(
                f"{fuel_id}: "
                f"durum={data.get('state', 'none')}, "
                f"teyit={data.get('verificationCount', 0)}"
            )
        else:
            print(f"{fuel_id}: kayit bulunamadi")


def main():
    db = initialize_firebase()
    check_fuel_data(db)
    print("Firebase baglanti testi tamamlandi.")
    print("Bu test bildirim gondermez ve veri degistirmez.")


if __name__ == "__main__":
    main()
