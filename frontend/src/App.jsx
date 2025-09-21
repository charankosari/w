// src/App.js
import React, { useState, useEffect } from "react";
import { CardanoWallet, useWallet, useAddress } from "@meshsdk/react";
import "./App.css";

const App = () => {
  const { connected, wallet } = useWallet();
  const address = useAddress();
  const [status, setStatus] = useState("");
  const [file, setFile] = useState(null);
  const [nfts, setNfts] = useState([]);
  const [loadingNfts, setLoadingNfts] = useState(false);

  useEffect(() => {
    const fetchNfts = async () => {
      if (connected && address) {
        setLoadingNfts(true);
        setStatus("Fetching your minted NFTs...");
        try {
          const response = await fetch(
            `http://localhost:5001/get-user-nfts/${address}`
          );
          if (!response.ok) throw new Error("Failed to fetch NFTs");
          const data = await response.json();
          setNfts(data);
          setStatus("NFTs loaded.");
        } catch (error) {
          console.error(error);
          setStatus(`Error: ${error.message}`);
        } finally {
          setLoadingNfts(false);
        }
      } else {
        setNfts([]); // Clear NFTs when wallet disconnects
      }
    };

    fetchNfts();
  }, [connected, address]);

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
  };

  const handleMint = async () => {
    if (!file) {
      setStatus("Please select an image file first.");
      return;
    }
    if (!connected) {
      setStatus("Please connect your wallet first.");
      return;
    }

    try {
      setStatus("Step 1/4: Preparing data...");
      const formData = new FormData();
      formData.append("file", file);
      // We get the address in hex format for pycardano
      const hexAddress = await wallet.getChangeAddress();
      formData.append("userAddress", hexAddress);

      setStatus("Step 2/4: Verifying image & building transaction...");
      const response = await fetch("http://localhost:5001/verify-and-mint", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "An error occurred at the backend.");
      }

      setStatus("Step 3/4: Please sign the transaction in your wallet...");
      const unsignedTx = data.txCbor;
      const signedTx = await wallet.signTx(unsignedTx);

      setStatus("Step 4/4: Submitting transaction to the blockchain...");
      const txHash = await wallet.submitTx(signedTx);

      setStatus(
        `Minting successful! TxHash: ${txHash}. Your new NFT will appear shortly.`
      );
      // After a successful mint, you might want to refresh the NFT list after a delay
      setTimeout(() => {
        // re-fetch NFTs
        if (address) {
          fetch(`http://localhost:5001/get-user-nfts/${address}`)
            .then((res) => res.json())
            .then((data) => setNfts(data));
        }
      }, 30000); // 30-second delay to allow transaction to process
    } catch (error) {
      console.error(error);
      setStatus(`Error: ${error.message}`);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>Authentic Image NFT Minter 🖼️</h1>
        <p>Mint NFTs on the Cardano Preprod Testnet after AI verification.</p>
        <div className="wallet-connector">
          <CardanoWallet />
        </div>
      </header>

      {connected && (
        <main>
          <div className="mint-section card">
            <h2>Mint a New NFT</h2>
            <input type="file" onChange={handleFileChange} accept="image/*" />
            <button onClick={handleMint}>Verify & Mint NFT</button>
          </div>

          <div className="status-section">
            <h3>Status</h3>
            <p>{status}</p>
          </div>

          <div className="gallery-section card">
            <h2>My Minted NFTs</h2>
            {loadingNfts ? (
              <p>Loading NFTs...</p>
            ) : nfts.length > 0 ? (
              <div className="nft-grid">
                {nfts.map((nft, index) => (
                  <div key={index} className="nft-card">
                    <img src={nft.image_url} alt={nft.name} />
                    <p>{nft.name}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p>You haven't minted any NFTs with this service yet.</p>
            )}
          </div>
        </main>
      )}

      {!connected && (
        <div className="connect-prompt">
          <h2>Please connect your wallet to begin.</h2>
        </div>
      )}
    </div>
  );
};

export default App;
