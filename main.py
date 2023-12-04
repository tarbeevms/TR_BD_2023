from flask import Flask, render_template, g, request, flash
from flask import redirect, url_for
import psycopg2
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.orm import aliased

# конфигурация
DATABASE = "FlowerShop"
DEBUG = True
SECRET_KEY = 'fdgfh78@#5?>gfhf89dx,v06k'
USERNAME = "postgres"
PASSWORD = "123"
HOST = "localhost"

app = Flask(__name__)
app.secret_key = SECRET_KEY

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@localhost/FlowerShop?client_encoding=utf8'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


def connect_db():
    conn = psycopg2.connect(dbname=DATABASE, user=USERNAME,
                            password=PASSWORD, host=HOST)
    return conn


def get_db():
    '''Соединение с БД, если оно еще не установлено'''
    if not hasattr(g, 'link_db'):
        g.link_db = connect_db()
    return g.link_db


@app.teardown_appcontext
def close_db(error):
    '''Закрываем соединение с БД, если оно было установлено'''
    if hasattr(g, 'link_db'):
        g.link_db.close()


@app.route("/FAQ")
def about():
    return render_template('about.html', title="О сайте")


class Employees(UserMixin, db.Model):
    employeeid = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(255), nullable=False)
    lastname = db.Column(db.String(255), nullable=False)
    post = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(255), nullable=False, unique=True)

    def get_id(self):
        return str(self.employeeid)


class Customers(db.Model):
    __tablename__ = 'customers'

    customerid = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(255))
    lastname = db.Column(db.String(255))
    customerstatus = db.Column(Enum('vip', 'common', name='typecustomerstatus'), default='common')
    monthlypurchaseamount = db.Column(db.Numeric(10, 2), default=0)
    phonenumber = db.Column(db.String(255))

    def __repr__(self):
        return f"<Customer(customerid={self.customerid}, firstname={self.firstname}, lastname={self.lastname}, " \
               f"customerstatus={self.customerstatus}, monthlypurchaseamount={self.monthlypurchaseamount}, " \
               f"phonenumber={self.phonenumber})>"


class Flowers(db.Model):
    flowerid = db.Column(db.Integer, primary_key=True)
    nameflower = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)


class Deliveryrates(db.Model):
    deliveryrateid = db.Column(db.Integer, primary_key=True)
    ratename = db.Column(db.String(255), nullable=False)
    deliverytimehours = db.Column(db.Integer)
    deliverycost = db.Column(db.Float, nullable=False)


class Payments(db.Model):
    orderid = db.Column(db.Integer, primary_key=True)
    paymentcost = db.Column(db.Float, nullable=False)
    paymentmethod = db.Column(db.String(255), nullable=False)
    paymentdescription = db.Column(db.String(255), nullable=False)
    orderstatus = db.Column(db.String(255), nullable=False, default='оплачен')
    paymentdate = db.Column(db.DateTime, default=datetime.utcnow)
    deliveryrateid = db.Column(db.Integer, db.ForeignKey('deliveryrates.deliveryrateid'))


class Orders(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customerid = db.Column(db.Integer, nullable=False)
    flowerid = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    ordernumber = db.Column(db.Integer, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return Employees.query.get(int(user_id))


@app.route("/auth", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Employees.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/view_revenue', methods=['GET'])
@login_required
def view_revenue():
    if current_user.post == 'владелец':
        cur = get_db().cursor()

        # Выполняем запрос к представлению
        cur.execute("SELECT * FROM revenue_summary;")

        # Получаем результат запроса
        result = cur.fetchall()
        print(result)
        # Закрываем курсор и соединение
        cur.close()
        get_db().close()
        return render_template('revenue.html', revenue=result)
    else:
        return f'''<h2>You have no permission to view revenue</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/")
def index():
    return render_template('index.html')


@app.route('/view_orders', methods=['GET', 'POST'])
@login_required
def view_orders():
    if current_user.post in ["менеджер", "владелец"]:

        # orders = Payments.query.all()

        orders = (
            db.session.query(Payments, Orders, Customers, Deliveryrates)
            .join(Orders, Payments.orderid == Orders.ordernumber)
            .join(Customers, Orders.customerid == Customers.customerid)
            .join(Deliveryrates, Payments.deliveryrateid == Deliveryrates.deliveryrateid)
            .filter(Payments.orderstatus.in_(['оплачен', 'доставляется']))  # Фильтрация по orderstatus
            .distinct(Payments.orderid)
            .all()
        )

        if request.method == 'POST':
            order_id = request.form['order_id']
            new_status = request.form['new_status']

            order = Payments.query.filter_by(orderid=order_id).first()
            if order:
                order.orderstatus = new_status
                db.session.commit()
            return redirect(url_for('view_orders'))
        return render_template('view_orders.html', orders=orders)
    else:
        return f'''<h2>You have no permission to view orders</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


@app.route('/create_order', methods=['GET', 'POST'])
@login_required
def create_order():
    flowers = Flowers.query.all()
    delivery_rates = Deliveryrates.query.all()

    if request.method == 'POST':
        flower_ids = request.form.getlist('flowers')
        flower_ids.extend(request.form.getlist('flowers[]'))
        quantities = request.form.getlist('quantities')
        quantities.extend(request.form.getlist('quantities[]'))
        delivery_address = request.form.get('delivery_address')
        delivery_rate_id = request.form.get('delivery_rate')
        payment_method = request.form.get('payment_method')
        order_firstname = request.form.get('first_name')
        order_lastname = request.form.get('last_name')
        order_description = request.form.get('order_description')
        customer_phone = request.form.get('customer_phone')

        # Рассчет общей стоимости, учитывая выбранные цветы и тариф доставки
        total_cost = calculate_total_cost(flower_ids, quantities, delivery_rate_id, customer_phone)

        # Вызов функции create_order_with_payment
        order_id = create_order_with_payment(
            request.form.get('customer_phone'),
            flower_ids,
            quantities,
            delivery_rate_id,
            delivery_address,
            payment_method,
            order_description,
            order_firstname,
            order_lastname,
            total_cost
        )
        try:
            cursor = get_db().cursor()
            cursor.execute('CALL reset_customer_purchase()')
            cursor.execute('CALL update_monthly_purchase_amount(%s::numeric, %s::varchar)',
                           (total_cost, customer_phone))
            get_db().commit()
        except Exception as e:
            # Обработка ошибок (например, запись в лог или вывод на экран)
            print(f"Error adding flower: {e}")
        finally:
            cursor.close()

    return render_template('create_order.html', flowers=flowers, delivery_rates=delivery_rates)


def create_order_with_payment(customer_phone, flower_ids, quantities, delivery_rate_id,
                              delivery_address, payment_method, order_description,
                              order_firstname, order_lastname, order_total_cost):
    try:
        # Создание курсора
        cur = get_db().cursor()
        # Формирование строки запроса с плейсхолдерами
        query = """
                    SELECT create_order_with_payment(
                        %s::VARCHAR, %s::INT[], %s::INT[], %s::INT, %s::VARCHAR, 
                        %s::TypePaymentMethod, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::NUMERIC
                    )
                """
        # Вызов функции
        cur.execute(query, (
            customer_phone,
            flower_ids,
            quantities,
            delivery_rate_id,
            delivery_address,
            payment_method,
            order_description,
            order_firstname,
            order_lastname,
            order_total_cost
        ))

        # Получение результата (если функция возвращает что-то)
        result = cur.fetchone()
        print(result)

        # Подтверждение изменений
        get_db().commit()

        # Fetch the result, assuming it's a single integer value
        order_id = result[0]
        return order_id
    except Exception as e:
        print("Error:", e)
        # Откат изменений в случае ошибки
        get_db().rollback()

    finally:
        # Закрытие курсора (или можете использовать конструкцию with)
        cur.close()


def calculate_total_cost(flower_ids, quantities, delivery_rate_id, customer_phone):
    try:
        flower_prices = {flower.flowerid: flower.price for flower in Flowers.query.all()}
        delivery_rate = Deliveryrates.query.get(delivery_rate_id).deliverycost
        customer = Customers.query.filter_by(phonenumber=customer_phone).first()
        if customer.customerstatus == 'vip':
            mult1 = 0.75
            mult2 = 0.7
        else:
            mult1 = 1
            mult2 = 1
        total_cost = 0.0

        for flower_id, quantity in zip(flower_ids, quantities):
            flower_id = int(flower_id)
            quantity = int(quantity)
            if flower_id in flower_prices:
                total_cost += quantity * flower_prices[flower_id] * mult1

        total_cost += delivery_rate * mult2  # Добавляем стоимость доставки

        return round(total_cost, 2)

    except Exception as e:
        print(f"Error calculating total cost: {e}")
        return None


@app.route('/view_customers')
def view_customers():
    if current_user.post == "владелец":
        customers = Customers.query.all()
        for customer in customers:
            print(customer.monthlypurchaseamount)
        return render_template('view_customers.html', customers=customers)
    else:
        return f'''<h2>You have no permission to view customers</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


@app.route('/add_flower', methods=['GET', 'POST'])
@login_required
def add_flower():
    if current_user.post == "владелец":
        if request.method == 'POST':
            name = request.form.get('name')
            price = request.form.get('price')
            try:
                cursor = get_db().cursor()
                cursor.execute('CALL add_flower(%s, %s)', (name, price))
                get_db().commit()
            except Exception as e:
                # Обработка ошибок (например, запись в лог или вывод на экран)
                print(f"Error adding flower: {e}")
            finally:
                cursor.close()
        return redirect(url_for('manage_flowers'))  # Перенаправляем на страницу управления цветами
    else:
        return f'''<h2>You have no permission to add flowers</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


# Пример для Flask
@app.route('/manage_flowers', methods=['GET', 'POST'])
@login_required
def manage_flowers():
    if current_user.post == "владелец":
        flowers = Flowers.query.all()

        if request.method == 'POST':
            # Обработка удаления цветка
            flower_id = request.form.get('flower_id')
            if flower_id:
                try:
                    cursor = get_db().cursor()
                    cursor.execute('CALL delete_flower(%s)', (flower_id,))
                    get_db().commit()
                except Exception as e:
                    # Обработка ошибок (например, запись в лог или вывод на экран)
                    print(f"Error deleting flower: {e}")
                finally:
                    cursor.close()

        return render_template('manage_flowers.html', flowers=flowers)
    else:
        return f'''<h2>You have no permission to manage flowers</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


@app.route('/delete_flower/<int:flower_id>', methods=['POST'])
@login_required
def delete_flower(flower_id):
    if current_user.post == "владелец":
        try:
            cursor = get_db().cursor()
            cursor.execute('CALL delete_flower(%s)', (flower_id,))
            get_db().commit()
        except Exception as e:
            # Обработка ошибок (например, запись в лог или вывод на экран)
            print(f"Error deleting flower: {e}")
        finally:
            cursor.close()

        return redirect(url_for('manage_flowers'))  # Перенаправляем на страницу управления цветами
    else:
        return f'''<h2>You have no permission to delete flowers</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


@app.route('/add_employee', methods=['POST', 'GET'])
@login_required
def add_employee():
    if current_user.post == "владелец":
        if request.method == 'POST':
            # Обработка добавления сотрудника
            firstname = request.form['firstname']
            lastname = request.form['lastname']
            post = request.form['post']
            password = request.form['password']
            username = request.form['username']

            new_employee = Employees(firstname=firstname, lastname=lastname, post=post, password=password,
                                     username=username)
            db.session.add(new_employee)
            db.session.commit()

        # Получите обновленный список сотрудников после добавления
        employees = Employees.query.all()
        return render_template('manage_employees.html', employees=employees)
    else:
        return f'''<h2>You have no permission to add employees</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


@app.route('/delete_employee', methods=['POST', 'GET'])
@login_required
def delete_employee():
    if current_user.post == "владелец":
        if request.method == 'POST':
            # Обработка удаления сотрудника
            employee_id = request.form['employee_id']
            employee = Employees.query.get(employee_id)

            if employee:
                db.session.delete(employee)
                db.session.commit()

        employees = Employees.query.all()
        return render_template('manage_employees.html', employees=employees)
    else:
        return f'''<h2>You have no permission to delete employees</h2><br>Your permission status is {current_user.post}. <a href="dashboard">Return to Dashboard</a>'''


if __name__ == "__main__":
    app.run(debug=True)
