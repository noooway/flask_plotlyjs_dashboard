import json
import sqlite3
import threading
import time
import datetime
import pandas as pd
from . import example_data


def init_data_sources(app):
    app.data_sources = {}
    register_dataframes(app)
    #import_csv(app)
    import_from_db(app)
    load_releases_info(app)
    init_datasource_with_update(app)


def register_dataframes(app):
    app.data_sources['revenue'] = example_data.revenue_df
    app.data_sources['installs'] = example_data.installs_df
    app.data_sources['regs'] = example_data.regs_df
    app.data_sources['online'] = example_data.online_df
    app.data_sources['first_sales'] = example_data.first_sales_df
    app.data_sources['sales'] = example_data.sales_df
    app.data_sources['virtual_currency_spent'] = \
        example_data.virtual_currency_spent_df
    app.data_sources['regs_to_first_sales'] = \
        example_data.regs_to_first_sales_df
    app.data_sources['first_sales_to_second_sales'] = \
        example_data.first_sales_to_second_sales_df


def import_csv(app):
    pass


def import_from_db(app):
    db_path = './data_sources_example/regs_pur.db'
    cohort_purchases_sql = """
    SELECT
        regs.reg_date AS reg_date,
        date(purchases.purchase_datetime) AS pur_date,
        SUM(purchase_amount) AS purchase_amount
    FROM purchases
    JOIN regs ON regs.id = purchases.reg_id
    GROUP BY regs.reg_date
    """
    db_conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    df = pd.read_sql_query(cohort_purchases_sql, db_conn)
    app.data_sources['regs_purchases'] = df
    db_conn.close()


def load_releases_info(app):
    releases_path = './data_sources_example/releases.json'
    with open(releases_path, 'r') as f:
        releases = json.load(f)
    app.data_sources['releases'] = releases['releases']


def init_datasource_with_update(app):
    app.data_sources['updated'] = None
    data_lock = threading.Lock()
    #todo: pass app or app.data_sources?
    #or pointer to element in app.data_sources?
    update_thread = threading.Thread(target=update_datasource,
                                     args=(app.data_sources, data_lock))
    # don't care much about proper exit for now;
    # don't forget to put connection timeout
    #todo: create table; drop on termination
    #test termination
    update_thread.setDaemon(True)
    update_thread.start()


def update_datasource(data_sources, lock):
    db_path = './data_sources_example/regs_pur.db'
    del_table_sql = 'DROP TABLE IF EXISTS updated;'
    create_sql = 'CREATE TABLE updated (vals REAL);'
    update_sql = 'INSERT INTO updated VALUES (?);'
    select_sql = 'SELECT * FROM updated;'
    #
    db_conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    cur = db_conn.cursor()
    cur.execute(del_table_sql)
    cur.execute(create_sql)
    db_conn.commit()
    #
    run_approx_every = 15.0
    counter = 5
    update_at_minutes = [1, 3]
    n_of_retries = 5
    retry_delay = 15
    wake_every = 30
    while True:
        current_minute = datetime.datetime.now().minute
        if current_minute in update_at_minutes and not already_updated:
            status = None
            for n in range(n_of_retries):
                # todo: check conn successfull
                # todo: put connection timeout
                status = False
                db_conn = sqlite3.connect(
                    db_path,
                    detect_types=sqlite3.PARSE_DECLTYPES
                )
                cur = db_conn.cursor()
                for n in range(5):
                    cur.execute(update_sql, [n * counter])
                    db_conn.commit()
                with lock:
                    data_sources['updated'] = pd.read_sql_query(select_sql, db_conn)
                    print(data_sources['updated'])
                    status = True
                db_conn.close()
                counter = counter + 1
                #
                if status:
                    already_updated = True
                    break
                else:
                    sleep(retry_delay)
        else:
            already_updated = False
            sleep(wake_every)
    db_conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    cur = db_conn.cursor()
    cur.execute(del_table_sql)
    db_conn.commit()
