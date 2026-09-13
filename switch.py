```python
# ===================================================================
# المحول المركزي (Central Switch)
# ===================================================================
import sqlite3
from datetime import datetime
import uuid

class CentralSwitch:
    """
    المحول المركزي: الوسيط بين البنوك.
    مسؤول عن:
    1. استقبال طلبات التحويل من البنوك.
    2. توليد رقم مرجعي فريد لكل عملية.
    3. تسجيل كل عملية في سجل مركزي.
    4. ضمان عدم ازدواجية العمليات.
    """
    
    def __init__(self, db_path='switch.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """إنشاء جداول قاعدة البيانات المركزية"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # جدول المعاملات المركزية
        c.execute('''
            CREATE TABLE IF NOT EXISTS central_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                from_bank TEXT NOT NULL,
                to_bank TEXT NOT NULL,
                from_account TEXT NOT NULL,
                to_account TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT
            )
        ''')
        
        # جدول التسويات (Settlement)
        c.execute('''
            CREATE TABLE IF NOT EXISTS settlements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_name TEXT NOT NULL,
                net_amount REAL DEFAULT 0,
                last_updated TEXT
            )
        ''')
        
        # إضافة البنوك إذا لم تكن موجودة
        for bank in ['bank_a', 'bank_b', 'bank_c']:
            c.execute('''
                INSERT OR IGNORE INTO settlements (bank_name, net_amount, last_updated)
                VALUES (?, 0, ?)
            ''', (bank, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print("✅ تم تهيئة المحول المركزي")
    
    def request_transfer(self, from_bank, to_bank, from_account, to_account, amount):
        """
        استقبال طلب تحويل من بنك.
        يعيد رقم مرجعي فريد إذا نجح الطلب.
        """
        # 1. التحقق من صحة البيانات
        if amount <= 0:
            return {"success": False, "error": "المبلغ يجب أن يكون أكبر من صفر"}
        
        if from_bank == to_bank:
            return {"success": False, "error": "لا يمكن التحويل داخل نفس البنك عبر المحول"}
        
        # 2. توليد رقم مرجعي فريد
        reference = str(uuid.uuid4())[:8].upper()
        
        # 3. تسجيل العملية في السجل المركزي
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO central_transactions 
            (reference, from_bank, to_bank, from_account, to_account, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (reference, from_bank, to_bank, from_account, to_account, amount, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        print(f"📤 المحول: استلم طلب تحويل {reference} من {from_bank} إلى {to_bank}")
        
        return {
            "success": True,
            "reference": reference,
            "message": f"تم استلام الطلب برقم مرجعي {reference}"
        }
    
    def confirm_transfer(self, reference):
        """
        تأكيد العملية بعد نجاح الخصم والإيداع في البنكين.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # جلب بيانات العملية
        c.execute('SELECT * FROM central_transactions WHERE reference = ?', (reference,))
        transaction = c.fetchone()
        
        if not transaction:
            conn.close()
            return {"success": False, "error": "العملية غير موجودة"}
        
        # تحديث حالة العملية
        c.execute('''
            UPDATE central_transactions 
            SET status = 'completed', completed_at = ?
            WHERE reference = ?
        ''', (datetime.now().isoformat(), reference))
        
        # تحديث التسويات (Settlement)
        from_bank = transaction[2]
        to_bank = transaction[3]
        amount = transaction[6]
        
        # البنك المرسل عليه دين للمحول، البنك المستقبل له رصيد
        c.execute('''
            UPDATE settlements 
            SET net_amount = net_amount - ?, last_updated = ?
            WHERE bank_name = ?
        ''', (amount, datetime.now().isoformat(), from_bank))
        
        c.execute('''
            UPDATE settlements 
            SET net_amount = net_amount + ?, last_updated = ?
            WHERE bank_name = ?
        ''', (amount, datetime.now().isoformat(), to_bank))
        
        conn.commit()
        conn.close()
        
        print(f"✅ المحول: تم تأكيد العملية {reference}")
        
        return {"success": True, "message": "تم تأكيد العملية"}
    
    def get_transaction(self, reference):
        """جلب تفاصيل عملية معينة"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM central_transactions WHERE reference = ?', (reference,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "reference": row[1],
            "from_bank": row[2],
            "to_bank": row[3],
            "from_account": row[4],
            "to_account": row[5],
            "amount": row[6],
            "status": row[7],
            "created_at": row[8],
            "completed_at": row[9]
        }
    
    def get_settlements(self):
        """عرض تسويات جميع البنوك"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT bank_name, net_amount, last_updated FROM settlements')
        rows = c.fetchall()
        conn.close()
        
        return [{"bank": r[0], "net_amount": r[1], "last_updated": r[2]} for r in rows]
    
    def get_all_transactions(self, limit=50):
        """عرض جميع المعاملات"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT reference, from_bank, to_bank, from_account, to_account, amount, status, created_at
            FROM central_transactions 
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        rows = c.fetchall()
        conn.close()
        
        return [{
            "reference": r[0], "from_bank": r[1], "to_bank": r[2],
            "from_account": r[3], "to_account": r[4], "amount": r[5],
            "status": r[6], "created_at": r[7]
        } for r in rows]
```
