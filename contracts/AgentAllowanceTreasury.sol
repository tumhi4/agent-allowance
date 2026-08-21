// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgentAllowanceTreasury
 * @notice EVM Escrow Vault releasing USDC disbursements upon GenLayer AI audit approval.
 */
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract AgentAllowanceTreasury {
    address public owner;
    address public genlayerRelay;
    IERC20 public usdcToken;

    event AgentPaymentDisbursed(string invoiceId, string agentId, address vendorAddress, uint256 amountUsdc);
    event AgentPaymentBlocked(string invoiceId, string agentId, string reason);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner authorized");
        _;
    }

    modifier onlyRelay() {
        require(msg.sender == genlayerRelay, "Only GenLayer Relay authorized");
        _;
    }

    constructor(address _usdcToken, address _genlayerRelay) {
        owner = msg.sender;
        usdcToken = IERC20(_usdcToken);
        genlayerRelay = _genlayerRelay;
    }

    function executeApprovedInvoice(
        string calldata invoiceId,
        string calldata agentId,
        address vendorAddress,
        uint256 amountUsdc
    ) external onlyRelay returns (bool) {
        require(vendorAddress != address(0), "Invalid vendor address");
        require(amountUsdc > 0, "Invalid amount");
        require(usdcToken.balanceOf(address(this)) >= amountUsdc, "Insufficient treasury balance");

        bool sent = usdcToken.transfer(vendorAddress, amountUsdc);
        require(sent, "USDC transfer failed");

        emit AgentPaymentDisbursed(invoiceId, agentId, vendorAddress, amountUsdc);
        return true;
    }
}
