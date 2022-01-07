sed -i '1s/^/127.0.0.1    test-server\n/' /etc/hosts
ktutil <<'EOF_'
read_kt /tmp/keytabs/user.keytab
read_kt /tmp/keytabs/service.keytab
write_kt /tmp/keytabs/krb5.keytab
EOF_
cp /tmp/keytabs/krb5.keytab /etc/krb5.keytab
chown -R root:root /etc/krb5.keytab
chmod 644 /etc/krb5.keytab
kinit httpuser@EXAMPLE.COM -k -t /tmp/keytabs/user.keytab
