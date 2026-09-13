
```python
# ===================================================================
# محاكي التحويلات البينية - التطبيق الرئيسي
# ===================================================================
from flask import Flask, render_template, request, jsonify, redirect, url_for
from switch import CentralSwitch
from bank_a import Bank
import os

app = Flask(__name__)

# تهيئة المكونات
switch = CentralSwitch('switch.db')

# إنشاء البنوك الثلاثة
bank_a = Bank("بنك الخرطوم", "bank_khartoum.db", switch)
bank_b = Bank("بنك فيصل", "bank_faisal.db", switch)
bank_c = Bank("بنك أمدرمان", "bank_omdurman.db", switch)

# قاموس لسهولة الوصول
banks = {
    "bank_khartoum": bank_a,
    "bank_faisal": bank_b,
    "bank_omdurman": bank_c
}

# أسماء عربية للعرض
bank_names = {
    "bank_khartoum": "بنك الخرطوم",
    "bank_faisal": "بنك فيصل",
    "bank_omdurman": "بنك أمدرمان"
}

# --------------------------------------------
# تهيئة بيانات تجريبية (مرة واحدة فقط)
# --------------------------------------------
def seed_data():
    """إضافة حسابات تجريبية إذا لم تكن موجودة"""
    if not bank_a.get_all_accounts():
        bank_a.create_account("KH001", "أحمد محمد", 50000)
        bank_a.create_account("KH002", "فاطمة علي", 30000)
    
    if not bank_b.get_all_accounts():
        bank_b.create_account("FS001", "محمد إبراهيم", 40000)
        bank_b.create_account("FS002", "سارة عثمان", 25000)
    
    if not bank_c.get_all_accounts():
        bank_c.create_account("OM001", "خالد يوسف", 60000)
        bank_c.create_account("OM002", "نور الهدى", 35000)

# --------------------------------------------
# المسارات (Routes)
# --------------------------------------------
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html', 
                         banks=bank_names,
                         settlements=switch.get_settlements())

@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    """صفحة التحويل"""
    if request.method == 'POST':
        from_bank_key = request.form.get('from_bank')
        from_account = request.form.get('from_account')
        to_bank_key = request.form.get('to_bank')
        to_account = request.form.get('to_account')
        amount = float(request.form.get('amount', 0))
        
        from_bank_obj = banks.get(from_bank_key)
        to_bank_obj = banks.get(to_bank_key)
        
        if not from_bank_obj or not to_bank_obj:
            return render_template('transfer.html', 
                                 banks=bank_names, 
                                 error="بنك غير صحيح")
        
        # 1. إرسال التحويل من البنك المرسل
        result = from_bank_obj.send_transfer(from_account, to_bank_key, to_account, amount)
        
        if not result["success"]:
            return render_template('transfer.html', 
                                 banks=bank_names, 
                                 error=result.get("error", "فشل التحويل"))
        
        reference = result["reference"]
        
        # 2. استقبال التحويل في البنك المستقبل
        receive_result = to_bank_obj.receive_transfer(reference, to_account, amount)
        
        if not receive_result["success"]:
            return render_template('transfer.html', 
                                 banks=bank_names, 
                                 error=receive_result.get("error", "فشل الاستقبال"))
        
        # 3. تأكيد العملية في المحول المركزي
        switch.confirm_transfer(reference)
        
        return render_template('transfer.html', 
                             banks=bank_names, 
                             success=f"✅ تم التحويل بنجاح! الرقم المرجعي: {reference}",
                             reference=reference)
    
    return render_template('transfer.html', banks=bank_names)

@app.route('/transactions')
def transactions():
    """عرض جميع المعاملات المركزية"""
    return render_template('transactions.html', 
                         transactions=switch.get_all_transactions(),
                         settlements=switch.get_settlements())

@app.route('/api/accounts/<bank_key>')
def api_accounts(bank_key):
    """API لجلب حسابات بنك معين"""
    bank_obj = banks.get(bank_key)
    if not bank_obj:
        return jsonify({"error": "بنك غير موجود"}), 404
    return jsonify(bank_obj.get_all_accounts())

@app.route('/api/balance/<bank_key>/<account_number>')
def api_balance(bank_key, account_number):
    """API لجلب رصيد حساب"""
    bank_obj = banks.get(bank_key)
    if not bank_obj:
        return jsonify({"error": "بنك غير موجود"}), 404
    balance = bank_obj.get_balance(account_number)
    if balance is None:
        return jsonify({"error": "حساب غير موجود"}), 404
    return jsonify({"account": account_number, "balance": balance})

# --------------------------------------------
# تشغيل التطبيق
# --------------------------------------------
if __name__ == '__main__':
    seed_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
```
