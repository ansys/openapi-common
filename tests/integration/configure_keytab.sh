#!/bin/bash
echo "------------------------------------------------"
echo "---- Configuring /etc/hosts --------------------"
echo "------------------------------------------------"
sed '1s/^/127.0.0.1    test-server\n/' /etc/hosts > ./hosts
cp ./hosts /etc/hosts

echo "------------------------------------------------"
echo "---- Copying keytabs to writeable location -----"
echo "------------------------------------------------"
cp /tmp/keytabs/user.keytab ./user.keytab
cp /tmp/keytabs/service.keytab ./service.keytab

echo "------------------------------------------------"
echo "---- Setting file permissions and owner --------"
echo "------------------------------------------------"
chown -R root:root ./user.keytab
chown -R root:root ./service.keytab
chmod 644 ./user.keytab
chmod 644 ./service.keytab

echo "------------------------------------------------"
echo "---- Writing combined keytab file --------------"
echo "------------------------------------------------"
ktutil <<'EOF_'
read_kt ./user.keytab
read_kt ./service.keytab
write_kt ./krb5.keytab
EOF_

echo "------------------------------------------------"
echo "---- Moving keytab and setting permissions -----"
echo "------------------------------------------------"
cp ./krb5.keytab /etc/krb5.keytab
chmod 644 /etc/krb5.keytab

echo "------------------------------------------------"
echo "---- Initialize ticket cache -------------------"
echo "------------------------------------------------"
kinit httpuser@EXAMPLE.COM -k -t ./user.keytab
