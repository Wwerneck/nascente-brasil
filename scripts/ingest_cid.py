"""Download and validate official DATASUS CID-10 DBF tables."""

from nascente_brasil.ingestion.cid import ingest_cid


if __name__ == "__main__":
    products, built = ingest_cid()
    print("CID tables built" if built else "CID tables already current")
    for name, item in products.items():
        print(name, item["records"], item["fields"], item["sha256"])
