import os
import io
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from blockfrost import BlockFrostApi, ApiError
from pycardano import (
    TransactionBuilder,
    TransactionOutput,
    Address,
    PlutusV2Script,
    MultiAsset,
    AssetName,
    script_hash,
    plutus_script_hash,
    Redeemer,
    RedeemerTag,
    Transaction,
)

# --- CONFIGURATION ---
BLOCKFROST_API_KEY = "preprodogfSo37F1XGN2rYSWbGfYp6UH3IIM4UQ"
WEB3_STORAGE_TOKEN = "Y6Jlcm9vdHOC2CpYJQABcRIguJwUAtUXu6Xql2dxd0_iPQxnnK2WQ374-E5KP-Ja9rfYKlglAAFxEiBznMN6nFV-QFK1bS0CiIJQkQivJAr3vVkIIFbAttviEGd2ZXJzaW9uAZAEAXESILicFALVF7ul6pdncXdP4j0MZ5ytlkN--PhOSj_iWva3qGFzRICgAwBhdmUwLjkuMWNhdHSBomNjYW5hKmR3aXRoZnVjYW46KmNhdWRZARCFJDCCAQoCggEBALZu83INTbKGipg8OVbg-OWwzeohZSXd4-XSzlPENzfRo2LG6NC5fteLylKCGGpeMEk1tkUye4d0ORUmHTnL-jQw4ZqT5RvvbriVPripk9hA-Nb_K2JkWPIHwsWD__wgsGyQNsMF9FFtTlnABR04fbN5oVd8QvHdw26-skLXRtNWERnrC7viHIkJYocbkVUNJ_P8pzCz0DsxAVVe9sHMACo5NqVffoSe5G-HwfePfYlIG_YKmMKWN6GTeQ3jBKvUwdqaCsZCr222TKixbbkzEcPNLa5hZzCYGgS_921viz8c35qyygW5GQoZ4RVY1lPr-aXTntSslJz8mh81MM2Va5sCAwEAAWNleHD2Y2ZjdIGibmFjY2Vzcy9jb25maXJt2CpYJQABcRIg5gOmE7jLjYQcvT4C_JLmLiWJCLxVuMoyFM4gZPZ6CaNuYWNjZXNzL3JlcXVlc3TYKlglAAFxEiBH5m1NlBRFhD-Zlh3Ke3I8u7S34YEb0peceNE4RH59L2Npc3NYJ50abWFpbHRvOmdtYWlsLmNvbTpzaGl2YWNoYXJhbmtvc2FyaTA5OWNwcmaAlgUBcRIgc5zDepxVfkBStW0tAoiCUJEIryQK971ZCCBWwLbb4hCoYXNYRO2hA0CCig3sD4aQklOcveQMod2R68ccJWM_pkWuFalWbSklFhYYbiLKwUmLY-yCg5N3H_pCDqlvoEPQ3otbuVawsOsFYXZlMC45LjFjYXR0gaNibmKhZXByb29m2CpYJQABcRIguJwUAtUXu6Xql2dxd0_iPQxnnK2WQ374-E5KP-Ja9rdjY2Fua3VjYW4vYXR0ZXN0ZHdpdGh4G2RpZDp3ZWI6dXAuc3RvcmFjaGEubmV0d29ya2NhdWRZARCFJDCCAQoCggEBALZu83INTbKGipg8OVbg-OWwzeohZSXd4-XSzlPENzfRo2LG6NC5fteLylKCGGpeMEk1tkUye4d0ORUmHTnL-jQw4ZqT5RvvbriVPripk9hA-Nb_K2JkWPIHwsWD__wgsGyQNsMF9FFtTlnABR04fbN5oVd8QvHdw26-skLXRtNWERnrC7viHIkJYocbkVUNJ_P8pzCz0DsxAVVe9sHMACo5NqVffoSe5G-HwfePfYlIG_YKmMKWN6GTeQ3jBKvUwdqaCsZCr222TKixbbkzEcPNLa5hZzCYGgS_921viz8c35qyygW5GQoZ4RVY1lPr-aXTntSslJz8mh81MM2Va5sCAwEAAWNleHD2Y2ZjdIGibmFjY2Vzcy9jb25maXJt2CpYJQABcRIg5gOmE7jLjYQcvT4C_JLmLiWJCLxVuMoyFM4gZPZ6CaNuYWNjZXNzL3JlcXVlc3TYKlglAAFxEiBH5m1NlBRFhD-Zlh3Ke3I8u7S34YEb0peceNE4RH59L2Npc3NYGZ0ad2ViOnVwLnN0b3JhY2hhLm5ldHdvcmtjcHJmgA"
MINTING_SCRIPT_HEX = "4e4d01000033222220051200120011"

plutus_script = PlutusV2Script(bytes.fromhex(MINTING_SCRIPT_HEX))
script_policy_id = plutus_script_hash(plutus_script)

# --- FLASK APP & BLOCKFROST API ---
app = Flask(__name__)
CORS(app)
api = BlockFrostApi(project_id=BLOCKFROST_API_KEY, base_url="https://cardano-preview.blockfrost.io/api")

# --- UPLOAD TO WEB3.STORAGE ---
def upload_to_web3_storage(file_bytes, filename):
    url = "https://api.web3.storage/upload"
    headers = {"Authorization": f"Bearer {WEB3_STORAGE_TOKEN}"}
    files = {"file": (filename, file_bytes)}
    response = requests.post(url, headers=headers, files=files)
    if response.status_code == 200 or response.status_code == 202:
        cid = response.json()["cid"]
        return cid
    else:
        raise Exception(f"Web3.Storage upload failed: {response.text}")

# --- MAIN ROUTE ---
@app.route("/create-unsigned-tx", methods=["POST"])
def create_unsigned_tx():
    if "userAddress" not in request.form or "file" not in request.files:
        return jsonify({"error": "Missing userAddress or file"}), 400

    try:
        user_address_hex = request.form["userAddress"]
        user_address = Address.from_primitive(bytes.fromhex(user_address_hex))
        file = request.files["file"]

        # 1. Upload file to Web3.Storage
        file_content = file.read()
        ipfs_hash = upload_to_web3_storage(file_content, file.filename)
        print(f"Successfully uploaded to Web3.Storage. CID: {ipfs_hash}")

        # 2. Prepare NFT metadata
        asset_name_str = file.filename.replace(" ", "")
        asset_name_bytes = AssetName(asset_name_str.encode("utf-8"))
        metadata = {
            721: {
                str(script_policy_id): {
                    asset_name_str: {
                        "name": file.filename,
                        "description": "An image verified on the Cardano blockchain.",
                        "mediaType": file.mimetype,
                        "image": f"ipfs://{ipfs_hash}"
                    }
                }
            }
        }

        # 3. Build transaction
        builder = TransactionBuilder(api)
        builder.add_input_address(user_address)
        builder.auxiliary_data = metadata

        my_asset = MultiAsset.from_primitive({
            bytes(script_policy_id): {asset_name_bytes: 1}
        })

        builder.mint = my_asset
        builder.add_script(plutus_script)
        builder.add_redeemer(Redeemer(0, RedeemerTag.MINT))

        min_val = builder.calculate_min_value(my_asset)
        builder.add_output(TransactionOutput(user_address, min_val + my_asset))

        signed_tx = builder.build_and_sign([], change_address=user_address)
        unsigned_tx = Transaction(signed_tx.transaction_body, signed_tx.transaction_witness_set)

        return jsonify({
            "txCbor": unsigned_tx.to_cbor("hex"),
            "policyId": str(script_policy_id),
            "assetName": asset_name_str
        })

    except ApiError as e:
        return jsonify({"error": f"Blockfrost API Error: {e.message}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
