```python
# ===================================================================
# نموذج بنك (Bank Template)
# ===================================================================
import sqlite3
from datetime import datetime

class Bank:
    """
    يمثل بنكاً واحداً في النظام.
    لكل بنك قاعدة بياناته المستقلة.
    """
    
    def __init__(self, name, db_path, switch=None):
        self.name = name
        self.db_path = db_path
        self.switch = switch
        self._init_db()
    
    def _init_db(self):
        """إنشاء جداول قاعدة بيانات البنك"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # جدول الحسابات
        c.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT UNIQUE NOT NULL,
                owner_name TEXT NOT NULL,
                balance REAL DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        # جدول المعاملات المحلية
        c.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT,
                type TEXT,
                from_account TEXT,
                to_account TEXT,
                amount REAL,
                status TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ تم تهيئة {self.name}")
    
    def create_account(self, account_number, owner_name, initial_balance=0):
        """إنشاء حساب جديد في البنك"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO accounts (account_number, owner_name, balance, created_at)
                VALUES (?, ?, ?, ?)
            ''', (account_number, owner_name, initial_balance, datetime.now().isoformat()))
            conn.commit()
            print(f"✅ {self.name}: تم إنشاء حساب {account_number} لـ {owner_name}")
            return {"success": True}
        except sqlite3.IntegrityError:
            return {"success": False, "error": "رقم الحساب موجود مسبقاً"}
        finally:
            conn.close()
    
    def get_balance(self, account_number):
        """جلب رصيد حساب"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT balance FROM accounts WHERE account_number = ?', (account_number,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    
    def _debit(self, account_number, amount):
        """خصم من حساب (داخلي)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT balance FROM accounts WHERE account_number = ?', (account_number,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return {"success": False, "error": "الحساب غير موجود"}
        
        if row[0] < amount:
            conn.close()
            return {"success": False, "error": "الرصيد غير كافٍ"}
        
        c.execute('UPDATE accounts SET balance = balance - ? WHERE account_number = ?', 
                  (amount, account_number))
        conn.commit()
        conn.close()
        return {"success": True}
    
    def _credit(self, account_number, amount):
        """إيداع في حساب (داخلي)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT balance FROM accounts WHERE account_number = ?', (account_number,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return {"success": False, "error": "الحساب غير موجود"}
        
        c.execute('UPDATE accounts SET balance = balance + ? WHERE account_number = ?', 
                  (amount, account_number))
        conn.commit()
        conn.close()
        return {"success": True}
    
    def send_transfer(self, from_account, to_bank_name, to_account, amount):
        """
        إرسال تحويل إلى بنك آخر عبر المحول المركزي.
        هذه هي العملية الأساسية في التشغيل البيني.
        """
        if not self.switch:
            return {"success": False, "error": "لا يوجد اتصال بالمحول المركزي"}
        
        # 1. التحقق من وجود الحساب والرصيد
        balance = self.get_balance(from_account)
        if balance is None:
            return {"success": False, "error": "الحساب المرسل غير موجود"}
        
        if balance < amount:
            return {"success": False, "error": "الرصيد غير كافٍ"}
        
        # 2. طلب التحويل من المحول المركزي
        result = self.switch.request_transfer(
            from_bank=self.name,
            to_bank=to_bank_name,
            from_account=from_account,
            to_account=to_account,
            amount=amount
        )
        
        if not result["success"]:
            return result
        
        reference = result["reference"]
        
        # 3. خصم المبلغ من حساب المرسل
        debit_result = self._debit(from_account, amount)
        if not debit_result["success"]:
            return debit_result
        
        # 4. تسجيل العملية محلياً
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO transactions (reference, type, from_account, to_account, amount, status, created_at)
            VALUES (?, 'outgoing', ?, ?, ?, 'pending', ?)
        ''', (reference, from_account, to_account, amount, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        print(f"📤 {self.name}: تم خصم {amount} من {from_account}، بانتظار تأكيد المحول")
        
        return {
            "success": True,
            "reference": reference,
            "message": f"تم إرسال التحويل برقم مرجعي {reference}"
        }
    
    def receive_transfer(self, reference, to_account, amount):
        """
        استقبال تحويل من بنك آخر.
        يتم استدعاؤها من المحول المركزي.
        """
        # 1. إيداع المبلغ في حساب المستقبل
        credit_result = self._credit(to_account, amount)
        if not credit_result["success"]:
            return credit_result
        
        # 2. تسجيل العملية محلياً
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO transactions (reference, type, from_account, to_account, amount, status, created_at)
            VALUES (?, 'incoming', ?, ?, ?, 'completed', ?)
        ''', (reference, "external", to_account, amount, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        print(f"📥 {self.name}: تم إيداع {amount} في {to_account}")
        
        return {"success": True}
    
    def get_transactions(self, limit=20):
        """عرض جميع معاملات البنك"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT reference, type, from_account, to_account, amount, status, created_at
            FROM transactions ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        rows = c.fetchall()
        conn.close()
        
        return [{
            "reference": r[0], "type": r[1], "from": r[2],
            "to": r[3], "amount": r[4], "status": r[5], "date": r[6]
        } for r in rows]
    
    def get_all_accounts(self):
        """عرض جميع الحسابات"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT account_number, owner_name, balance FROM accounts')
        rows = c.fetchall()
        conn.close()
        
        return [{"account": r[0], "owner": r[1], "balance": r[2]} for r in rows]
```
