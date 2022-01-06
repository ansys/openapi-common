sudo sed -i '1s/^/127.0.0.1    test-server\n/' /etc/hosts
docker cp kerberos-kdc-server-1:/service.keytab ./service.keytab
docker cp kerberos-kdc-server-1:/user.keytab ./user.keytab
ktutil <<'EOF_'
read_kt ./user.keytab
read_kt ./service.keytab
write_kt ./krb5.keytab
EOF_
sudo cp ./krb5.keytab /etc/krb5.keytab
sudo chmod 644 /etc/krb5.keytab
kinit httpuser@EXAMPLE.COM -k -t ./user.keytab

