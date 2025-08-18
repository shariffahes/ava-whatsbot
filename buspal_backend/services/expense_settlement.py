from typing import List, Dict, Optional
from collections import defaultdict
from buspal_backend.models.expense import ExpenseModel
import heapq
from bson import ObjectId

class ExpenseSettlementService:
    
    @staticmethod
    def _convert_objectids_to_strings(obj):
        """Convert ObjectIds to strings recursively"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {key: ExpenseSettlementService._convert_objectids_to_strings(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [ExpenseSettlementService._convert_objectids_to_strings(item) for item in obj]
        else:
            return obj
    
    @staticmethod
    def calculate_net_balances(expenses: List[Dict]) -> Dict[str, Dict]:
        """Calculate net balance for each person (positive = should receive, negative = should pay)"""
        balances = defaultdict(lambda: {"amount": 0.0, "name": ""})
        
        for expense in expenses:
            payer_id = expense["payer_id"]
            total_amount = expense["total_amount"]
            participants = expense["participants"]
            
            # Add the amount paid by the payer
            balances[payer_id]["amount"] += total_amount
            balances[payer_id]["name"] = expense["payer_name"]
            
            # Subtract each participant's share
            for participant in participants:
                user_id = participant["user_id"]
                share_amount = participant["share_amount"]
                balances[user_id]["amount"] -= share_amount
                balances[user_id]["name"] = participant["name"]
        
        return dict(balances)
    
    @staticmethod
    def minimize_transactions(balances: Dict[str, Dict]) -> List[Dict]:
        """
        Minimize number of transactions using debt minimization algorithm
        Returns list of transactions: [{"from": user_id, "from_name": str, "to": user_id, "to_name": str, "amount": float}]
        """
        # Filter out zero balances
        non_zero_balances = {k: v for k, v in balances.items() if abs(v["amount"]) > 0.01}
        
        if not non_zero_balances:
            return []
        
        # Create heaps for creditors (max heap) and debtors (min heap)
        creditors = []  # People who should receive money
        debtors = []    # People who should pay money
        
        for user_id, balance_info in non_zero_balances.items():
            balance = balance_info["amount"]
            if balance > 0:
                heapq.heappush(creditors, (-balance, user_id))  # Negative for max heap
            else:
                heapq.heappush(debtors, (balance, user_id))     # Positive for min heap
        
        transactions = []
        
        while creditors and debtors:
            # Get the person who should receive the most and owes the most
            creditor_balance, creditor_id = heapq.heappop(creditors)
            debtor_balance, debtor_id = heapq.heappop(debtors)
            
            creditor_amount = -creditor_balance
            debtor_amount = -debtor_balance
            
            # Settle the smaller amount
            settlement_amount = min(creditor_amount, debtor_amount)
            
            transactions.append({
                "from": debtor_id,
                "from_name": balances[debtor_id]["name"],
                "to": creditor_id,
                "to_name": balances[creditor_id]["name"],
                "amount": round(settlement_amount, 2)
            })
            
            # Update balances
            remaining_creditor = creditor_amount - settlement_amount
            remaining_debtor = debtor_amount - settlement_amount
            
            # Re-add to heaps if there's remaining balance
            if remaining_creditor > 0.01:
                heapq.heappush(creditors, (-remaining_creditor, creditor_id))
            if remaining_debtor > 0.01:
                heapq.heappush(debtors, (-remaining_debtor, debtor_id))
        
        return transactions
    
    @staticmethod
    def calculate_settlements(convo_id: str, include_settled: bool = False) -> Dict:
        expenses = ExpenseModel.get_by_convo_id(convo_id, include_settled)
        
        if not expenses:
            return {
                "balances": {},
                "transactions": [],
                "total_expenses": 0,
                "summary": "No expenses found"
            }
        
        # Calculate net balances
        balances = ExpenseSettlementService.calculate_net_balances(expenses)

        # Calculate total expenses
        total_expenses = sum(expense["total_amount"] for expense in expenses)
        
        # Get optimal transactions
        transactions = ExpenseSettlementService.minimize_transactions(balances)
        
        # Create summary
        summary = ExpenseSettlementService.create_settlement_summary(
            balances, transactions, total_expenses
        )
        
        # Convert ObjectIds to strings for JSON serialization
        serializable_expenses = ExpenseSettlementService._convert_objectids_to_strings(expenses)
        
        return {
            "balances": balances,
            "transactions": transactions,
            "total_expenses": total_expenses,
            "summary": summary,
            "expenses": serializable_expenses
        }
    
    @staticmethod
    def create_settlement_summary(balances: Dict[str, Dict], 
                                transactions: List[Dict], 
                                total_expenses: float) -> str:
        """Create a human-readable settlement summary"""
        if not transactions:
            return f"💰 Total expenses: ${total_expenses:.2f}\n✅ All settled! No payments needed."
        
        summary = [f"💰 Total expenses: ${total_expenses:.2f}\n"]
        summary.append("💳 Settlement Plan:")
        
        for i, transaction in enumerate(transactions, 1):
            summary.append(
                f"{i}. {transaction['from_name']} pays ${transaction['amount']:.2f} to {transaction['to_name']}"
            )
        
        return "\n".join(summary)
    
    @staticmethod
    def add_expense(convo_id: str, description: str, total_amount: float,
                   payer_id: str, payer_name: str, participants: List[Dict],
                   expense_type: str = "equal") -> Dict:
        """
        Add a new expense to the conversation
        participants: [{"user_id": str, "name": str, "share_amount": float}]
        """
        # Validate participants
        total_shares = sum(p["share_amount"] for p in participants)
        if abs(total_shares - total_amount) > 0.01:
            raise ValueError(f"Participant shares ({total_shares}) don't match total amount ({total_amount})")
        
        # Create expense
        expense = ExpenseModel.create(
            convo_id=convo_id,
            description=description,
            total_amount=total_amount,
            payer_id=payer_id,
            payer_name=payer_name,
            participants=participants,
            expense_type=expense_type
        )
        
        return expense
    
    @staticmethod
    def split_equally(total_amount: float, participants: List[Dict]) -> List[Dict]:
        """Split amount equally among participants"""
        if not participants:
            return []
        
        per_person = total_amount / len(participants)
        
        for participant in participants:
            participant["share_amount"] = round(per_person, 2)
        
        # Handle rounding by adjusting the last participant
        total_shares = sum(p["share_amount"] for p in participants)
        if abs(total_shares - total_amount) > 0.01:
            participants[-1]["share_amount"] += round(total_amount - total_shares, 2)
        
        return participants
    
    @staticmethod
    def get_expense_history(convo_id: str, limit: int = 10) -> List[Dict]:
        """Get recent expense history for a conversation"""
        expenses = ExpenseModel.get_by_convo_id(convo_id, include_settled=True)
        return expenses[:limit]
    
    @staticmethod
    def settle_payments(convo_id: str, expense_ids: Optional[List[str]] = None) -> Dict:
        """Mark expenses as settled - either all or specific ones"""
        try:
            if expense_ids:
                # Settle specific expenses
                settled_count = 0
                for expense_id in expense_ids:
                    ExpenseModel.mark_settled(expense_id)
                    settled_count += 1
                
                return {
                    "success": True,
                    "message": f"Successfully settled {settled_count} specific expenses",
                    "settled_count": settled_count
                }
            else:
                # Settle all unsettled expenses
                expenses = ExpenseModel.get_by_convo_id(convo_id, include_settled=False)
                
                if not expenses:
                    return {
                        "success": True,
                        "message": "No unsettled expenses found",
                        "settled_count": 0
                    }
                
                # Mark all expenses as settled
                settled_count = 0
                for expense in expenses:
                    ExpenseModel.mark_settled(expense["_id"])
                    settled_count += 1
                
                return {
                    "success": True,
                    "message": f"Successfully settled all {settled_count} expenses",
                    "settled_count": settled_count
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to settle payments: {str(e)}",
                "settled_count": 0
            }
    
    @staticmethod
    def get_user_balance_summary(convo_id: str, user_id: str) -> Dict:
        """Get balance summary for a specific user"""
        settlement_data = ExpenseSettlementService.calculate_settlements(convo_id)
        balances = settlement_data["balances"]
        transactions = settlement_data["transactions"]
        
        user_balance_info = balances.get(user_id, {"amount": 0, "name": ""})
        user_balance = user_balance_info["amount"]
        
        # Find transactions involving this user
        user_transactions = [
            t for t in transactions 
            if t["from"] == user_id or t["to"] == user_id
        ]
        
        return {
            "user_id": user_id,
            "name": user_balance_info["name"],
            "net_balance": user_balance,
            "transactions": user_transactions,
            "status": "creditor" if user_balance > 0 else "debtor" if user_balance < 0 else "settled"
        }