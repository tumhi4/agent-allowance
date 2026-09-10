import { createClient } from '../../AetherDungeon/frontend/node_modules/genlayer-js/dist/index.js';

async function testLive() {
    const client = createClient({ endpoint: 'https://studio.genlayer.com/api' });
    const contractAddress = '0xEFF74aBcfa4006C2601aDaEcb259700ef1870e89';
    console.log("Testing live view on deployed contract:", contractAddress);
    
    try {
        const policy = await client.readContract({
            address: contractAddress,
            functionName: 'get_agent_policy',
            args: ['AGENT_RESEARCH_01']
        });
        console.log("Genesis Policy from Live Contract:", JSON.stringify(policy, (k, v) => typeof v === 'bigint' ? v.toString() : v, 2));
        
        const total = await client.readContract({
            address: contractAddress,
            functionName: 'get_total_audited',
            args: []
        });
        console.log("Total Audited from Live Contract:", total.toString());
        console.log(">>> LIVE ON-CHAIN CONTRACT TEST PASSED! <<<");
    } catch (err) {
        console.error("Live test error:", err);
    }
}

testLive();
