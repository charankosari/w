import os
import io
import requests
import random
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from blockfrost import BlockFrostApi, ApiError
from pycardano import (
    TransactionBuilder, TransactionOutput, Address, PlutusV2Script,
    MultiAsset, plutus_script_hash, Redeemer, RedeemerTag, Transaction,
    AuxiliaryData, PlutusData
)
from importlib.metadata import version, PackageNotFoundError

# --- DEBUGGING INFO ---
try:
    pycardano_version = version("pycardano")
except PackageNotFoundError:
    pycardano_version = "Not installed or found"
print("--- SCRIPT DEBUG INFO ---")
print(f"PyCardano Version Loaded: {pycardano_version}")
print("--------------------------")

# --- INITIALIZATION ---
load_dotenv()
app = Flask(__name__)
CORS(app)  # Allow requests from our React frontend

# --- CONFIGURATION ---
BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_API_KEY")
PINATA_JWT = os.getenv("PINATA_JWT")

# A simple PlutusV2 script that always allows minting.
MINTING_SCRIPT_HEX = "4e4d01000033222220051200120011"
plutus_script = PlutusV2Script(bytes.fromhex(MINTING_SCRIPT_HEX))
MINTING_POLICY_ID = str(plutus_script_hash(plutus_script))

try:
    api = BlockFrostApi(
        project_id=BLOCKFROST_API_KEY,
        # Ensure you are using the correct network API URL
        base_url="https://cardano-preprod.blockfrost.io/api/v0"
    )
except Exception as e:
    print(f"Failed to initialize Blockfrost API: {e}")
    api = None

# --- HELPER FUNCTIONS ---

def is_ai_generated(image_bytes: bytes) -> bool:
    """
    *** DUMMY AI CHECK ***
    Replace this with a real AI detection model in a production environment.
    """
    print("Performing dummy AI verification...")
    return random.random() < 0.10

def upload_to_pinata(file_bytes, filename):
    """Uploads a file to IPFS via Pinata."""
    print(f"Uploading {filename} to Pinata...")
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}
    files = {'file': (filename, file_bytes)}
    
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()  # Raise an exception for HTTP errors
    
    ipfs_hash = response.json()["IpfsHash"]
    print(f"Upload successful. IPFS Hash: {ipfs_hash}")
    return ipfs_hash

# --- API ROUTES ---

@app.route("/verify-and-mint", methods=["POST"])
def verify_and_mint():
    if not api:
        return jsonify({"error": "Backend server is not configured correctly. Check API keys."}), 500
        
    if "userAddress" not in request.form or "file" not in request.files:
        return jsonify({"error": "Missing userAddress or file"}), 400

    try:
        # Step 1: Get data from the request
        user_address_hex = request.form["userAddress"]
        user_address = Address.from_primitive(bytes.fromhex(user_address_hex))
        file = request.files["file"]
        file_content = file.read()

        # Step 2: Perform checks and upload
        if is_ai_generated(file_content):
            return jsonify({"error": "AI-generated image detected. Minting rejected."}), 403

        ipfs_hash = upload_to_pinata(file_content, file.filename)

        # Step 3: Prepare asset name and metadata
        asset_name_str = os.path.splitext(file.filename)[0].replace(" ", "_")
        asset_name_bytes = asset_name_str.encode("utf-8")[:32]
        
        metadata = {
            721: {
                bytes.fromhex(MINTING_POLICY_ID): {
                    asset_name_bytes: {
                        "name": file.filename,
                        "description": "An authentic image verified on the Cardano blockchain.",
                        "mediaType": file.mimetype,
                        "image": f"ipfs://{ipfs_hash}"
                    }
                }
            }
        }

        # Step 4: Build the transaction
        builder = TransactionBuilder(api)
        builder.add_input_address(user_address) # Simplified UTxO handling
        builder.auxiliary_data = AuxiliaryData(PlutusData.from_primitive(metadata))

        my_asset = MultiAsset.from_primitive({
            bytes.fromhex(MINTING_POLICY_ID): {
                asset_name_bytes: 1
            }
        })
        builder.mint = my_asset
        
        # **CRITICAL FIX**: Correctly structure the Redeemer
        # The index=0 points to the first (and only) minting script
        builder.minting_scripts = [plutus_script]
        builder.redeemers = [Redeemer(tag=RedeemerTag.MINT, data=PlutusData.from_primitive(0), index=0)]

        # Add an output that sends the newly minted token back to the user
        # The builder will automatically calculate the minimum ADA for this output
        output = TransactionOutput(user_address, my_asset)
        builder.add_output(output)
        
        # Build the transaction body. The builder will automatically select inputs,
        # calculate fees, and create a change output.
        tx_body = builder.build(change_address=user_address)
        unsigned_tx = Transaction(tx_body, None)

        return jsonify({
            "message": "Verification successful! Please sign the transaction.",
            "txCbor": unsigned_tx.to_cbor("hex"),
        })

    except ApiError as e:
        print(f"[ERROR] Blockfrost API Error: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Blockfrost API Error: {str(e)}"}), 500
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred in verify_and-mint: {e}")
        traceback.print_exc()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/get-user-nfts/addr_test1vzpwq95z3xyum8vqndgdd9mdnmafh3djcxnc6jemlgdmswcve6tkw", methods=["GET"])
def get_user_nfts(wallet_address):
    w="addr_test1vzpwq95z3xyum8vqndgdd9mdnmafh3djcxnc6jemlgdmswcve6tkw"
    if not api:
        return jsonify({"error": "Backend server is not configured correctly. Check API keys."}), 500

    try:
        utxos = api.address_utxos(address=w)
        print(utxos)
        all_asset_units = set()
        for utxo in utxos:
            for asset in utxo.amount:
                if asset.unit != 'lovelace':
                    all_asset_units.add(asset.unit)
        
        owned_nft_units = [unit for unit in all_asset_units if unit.startswith(MINTING_POLICY_ID)]
        
        nft_details = []
        for nft_unit in owned_nft_units:
            try:
                asset_info = api.asset(asset=nft_unit)
                metadata = asset_info.onchain_metadata
                if metadata and metadata.get("image"):
                    nft_details.append({
                        "name": metadata.get("name", "Unnamed NFT"),
                        "image_url": metadata.get("image", "").replace("ipfs://", "https://gateway.pinata.cloud/ipfs/"),
                    })
            except ApiError as asset_e:
                print(f"Could not fetch metadata for asset {nft_unit}: {asset_e}")

        return jsonify(nft_details)
        
    except ApiError as e:
        if e.status_code == 404:
            return jsonify([]) # Address not found on-chain, return empty list
        return jsonify({"error": f"Blockfrost API Error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)