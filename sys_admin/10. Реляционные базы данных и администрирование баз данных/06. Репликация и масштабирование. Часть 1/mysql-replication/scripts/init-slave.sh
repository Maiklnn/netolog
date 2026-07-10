#!/bin/bash
set -e

echo "========================================="
echo "  MySQL Replication Setup Script"
echo "========================================="

# Ожидание готовности мастера
echo "Ожидание готовности MySQL Master..."
until mysql -h mysql_master -u root -proot123 -e "SELECT 1" > /dev/null 2>&1; do
  echo "Master не готов, ожидаем..."
  sleep 3
done

echo "✅ MySQL Master готов!"

# Создание пользователя для репликации
echo "Создание пользователя replicator на мастере..."
mysql -h mysql_master -u root -proot123 <<-EOSQL
  CREATE USER IF NOT EXISTS 'replicator'@'%' IDENTIFIED BY 'replica_pass';
  GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'replicator'@'%';
  FLUSH PRIVILEGES;
EOSQL

echo "✅ Пользователь replicator создан!"

# Получение статуса мастера
echo "Получение статуса мастера..."
MASTER_FILE=$(mysql -h mysql_master -u root -proot123 -e "SHOW MASTER STATUS\G" | grep "File:" | awk '{print $2}')
MASTER_POS=$(mysql -h mysql_master -u root -proot123 -e "SHOW MASTER STATUS\G" | grep "Position:" | awk '{print $2}')

echo "Master File: $MASTER_FILE"
echo "Master Position: $MASTER_POS"

# Настройка репликации на слейве
echo "========================================="
echo "Настройка репликации на слейве..."
echo "========================================="

mysql -u root -proot123 <<-EOSQL
  STOP SLAVE;
  RESET SLAVE;

  CHANGE MASTER TO
    MASTER_HOST='mysql_master',
    MASTER_PORT=3306,
    MASTER_USER='replicator',
    MASTER_PASSWORD='replica_pass',
    MASTER_LOG_FILE='$MASTER_FILE',
    MASTER_LOG_POS=$MASTER_POS;

  START SLAVE;
EOSQL

echo "✅ Репликация настроена!"

# Проверка статуса
echo "========================================="
echo "Статус репликации:"
echo "========================================="
mysql -u root -proot123 -e "SHOW SLAVE STATUS\G" | grep -E "Slave_IO_Running|Slave_SQL_Running|Seconds_Behind_Master|Last_Error|Last_IO_Error|Last_SQL_Error"

echo "========================================="
echo "🎉 Инициализация реплики завершена!"
echo "========================================="
