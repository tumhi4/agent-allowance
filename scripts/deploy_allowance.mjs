import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createClient, createAccount } from '../../AetherDungeon/frontend/node_modules/genlayer-js/dist/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
    console.log("Connecting to GenLayer Studio RPC: https://studio.genlayer.com/api");
    const account = createAccount();
    console.log("Generated Deployer Account:", account.address);
    
    const client = createClient({
        endpoint: 'https://studio.genlayer.com/api',
        account: account
    });
    
    const contractPath = path.join(__dirname, '..', 'contracts', 'AgentAllowance.py');
    const code = fs.readFileSync(contractPath, 'utf8');
    console.log(`Read contract code (${code.length} bytes)`);
    
    const operator = account.address;
    console.log("Setting operator to:", operator);
    
    console.log("Broadcasting deployContract transaction to GenLayer...");
    try {
        const txHash = await client.deployContract({
            code: code,
            args: [operator]
        });
        console.log("Deployment transaction submitted! Tx Hash:", txHash);
        
        console.log("Waiting for transaction receipt on GenLayer...");
        const receipt = await client.waitForTransactionReceipt({
            hash: txHash,
            status: 'FINALIZED',
            interval: 3000,
            retries: 40
        });
        console.log("Receipt status:", receipt.status);
        const contractAddress = receipt.contractAddress || receipt.data?.contractAddress || receipt.recipient;
        console.log("Contract Address:", contractAddress);
        console.log("Receipt details:", JSON.stringify(receipt, (key, value) => typeof value === 'bigint' ? value.toString() : value, 2));
        
        if (contractAddress) {
            console.log("\n>>> DEPLOYMENT SUCCESSFUL! <<<");
            console.log("Contract Address:", contractAddress);
            console.log("Explorer URL: https://explorer-studio.genlayer.com/address/" + contractAddress);
        }
    } catch (err) {
        console.error("Deploy failed:", err);
    }
}

main();
