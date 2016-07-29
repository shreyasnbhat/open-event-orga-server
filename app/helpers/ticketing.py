"""Copyright 2016 Niranjan Rajendran"""
import binascii
import os

from datetime import timedelta, datetime
from sqlalchemy import func

from app.helpers.data import save_to_db
from app.helpers.helpers import string_empty
from app.models.order import Order
from app.models.ticket import Ticket
from app.helpers.data_getter import DataGetter
from app.helpers.data import DataManager

from app.models.ticket_holder import TicketHolder
from app.models.order import OrderTicket
from app.models.user_detail import UserDetail
from app.helpers.helpers import send_email_after_account_create_with_password


def get_count(q):
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count

def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


class TicketingManager(object):
    """All ticketing and orders related functions"""

    @staticmethod
    def get_order_expiry():
        return 10

    @staticmethod
    def get_new_order_identifier():
        identifier = binascii.b2a_hex(os.urandom(32))
        count = get_count(Order.query.filter_by(identifier=identifier))
        if count == 0:
            return identifier
        else:
            return TicketingManager.get_new_order_identifier()

    @staticmethod
    def get_ticket(ticket_id):
        return Ticket.query.get(ticket_id)

    @staticmethod
    def get_order(order_id):
        return Ticket.query.get(order_id)

    @staticmethod
    def get_order_by_identifier(identifier):
        return Order.query.filter_by(identifier=identifier).one()

    @staticmethod
    def get_or_create_user_by_email(email, data=None):
        user = DataGetter.get_user_by_email(email, False)
        if not user:
            password = binascii.b2a_hex(os.urandom(4))
            user_data = []
            user_data[0] = email
            user_data[1] = password
            user = DataManager.create_user(user_data)
            send_email_after_account_create_with_password({
                'email': email,
                'password': password
            })
        if user.user_detail:
            user.user_detail.fullname = data['firstname'] + ' ' + data['lastname']
        else:
            user_detail = UserDetail(fullname=data['firstname'] + ' ' + data['lastname'])
            user.user_detail = user_detail

        save_to_db(user)
        return user

    @staticmethod
    def get_and_set_expiry(identifier, override=False):
        if type(identifier) is Order:
            order = identifier
        elif represents_int(identifier):
            order = TicketingManager.get_order(identifier)
        else:
            order = TicketingManager.get_order_by_identifier(identifier)

        if order:
            if override \
                or (order.state == 'pending' and
                    (order.created_at + timedelta(minutes=TicketingManager.get_order_expiry())) < datetime.now()):
                order.state = 'expired'
                save_to_db(order)
        return order

    @staticmethod
    def create_order(form):
        order = Order()
        order.state = 'pending'
        order.identifier = TicketingManager.get_new_order_identifier()
        order.event_id = form.get('event_id')
        ticket_ids = form.getlist('ticket_ids[]')

        ticket_quantity = form.getlist('ticket_quantities[]')
        amount = 0
        for index, id in enumerate(ticket_ids):
            if not string_empty(id) and int(ticket_quantity[index]) > 0:
                order_ticket = OrderTicket()
                order_ticket.ticket = TicketingManager.get_ticket(id)
                order_ticket.quantity = int(ticket_quantity[index])
                order.tickets.append(order_ticket)
                amount = amount + (order_ticket.ticket.price * order_ticket.quantity)

        order.amount = amount

        save_to_db(order)
        return order

    @staticmethod
    def initiate_order_payment(form):
        identifier = form['identifier']
        first_name = form['firstname']
        last_name = form['lastname']
        email = form['email']
        country = form['country']
        address = form['address']
        city = form['city']
        state = form['state']
        zipcode = form['zipcode']
        order = TicketingManager.get_and_set_expiry(identifier)
        if order:
            user = TicketingManager.get_or_create_user_by_email(email, form)
            order.user_id = user.id
            order.address = address
            order.city = city
            order.state = state
            order.country = country
            order.zipcode = zipcode
            order.state = 'initialized'
            save_to_db(order)
            return order
        else:
            return False
