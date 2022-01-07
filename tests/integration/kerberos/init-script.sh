#!/bin/bash
echo "==================================================================================="
echo "==== Kerberos KDC and Kadmin ======================================================"
echo "==================================================================================="
KADMIN_PRINCIPAL_FULL=$KADMIN_PRINCIPAL@$REALM

echo "REALM: $REALM"
echo "KADMIN_PRINCIPAL_FULL: $KADMIN_PRINCIPAL_FULL"
echo "KADMIN_PASSWORD: $KADMIN_PASSWORD"
echo ""

echo "==================================================================================="
echo "==== /etc/krb5.conf ==============================================================="
echo "==================================================================================="
KDC_KADMIN_SERVER=$(hostname -f)
tee /etc/krb5.conf <<EOF
[libdefaults]
	default_realm = $REALM

[realms]
	$REALM = {
		kdc_ports = 88,750
		kadmind_port = 749
		kdc = $KDC_KADMIN_SERVER
		admin_server = $KDC_KADMIN_SERVER
	}
EOF
echo ""

echo "==================================================================================="
echo "==== /etc/krb5kdc/kdc.conf ========================================================"
echo "==================================================================================="
tee /etc/krb5kdc/kdc.conf <<EOF
[realms]
	$REALM = {
		acl_file = /etc/krb5kdc/kadm5.acl
		max_renewable_life = 7d 0h 0m 0s
		supported_enctypes = $SUPPORTED_ENCRYPTION_TYPES
		default_principal_flags = +preauth
	}
EOF
echo ""

echo "==================================================================================="
echo "==== /etc/krb5kdc/kadm5.acl ======================================================="
echo "==================================================================================="
tee /etc/krb5kdc/kadm5.acl <<EOF
$KADMIN_PRINCIPAL_FULL *
noPermissions@$REALM X
EOF
echo ""

echo "==================================================================================="
echo "==== Creating realm ==============================================================="
echo "==================================================================================="
MASTER_PASSWORD=$(tr -cd '[:alnum:]' < /dev/urandom | fold -w30 | head -n1)
# This command also starts the krb5-kdc and krb5-admin-server services
krb5_newrealm <<EOF
$MASTER_PASSWORD
$MASTER_PASSWORD
EOF
echo ""

echo "==================================================================================="
echo "==== Creating default principals in the acl ======================================="
echo "==================================================================================="
echo "Adding $KADMIN_PRINCIPAL principal"
kadmin.local -q "delete_principal -force $KADMIN_PRINCIPAL_FULL"
echo ""
kadmin.local -q "addprinc -pw $KADMIN_PASSWORD $KADMIN_PRINCIPAL_FULL"
echo ""

echo "Adding noPermissions principal"
kadmin.local -q "delete_principal -force noPermissions@$REALM"
echo ""
kadmin.local -q "addprinc -pw $KADMIN_PASSWORD noPermissions@$REALM"
echo ""

echo "=================================================================================="
echo "==== Creating user and service principals for testing ============================"
echo "=================================================================================="
echo "Adding httpuser account"
USER_PASSWORD=$(tr -cd '[:alnum:]' < /dev/urandom | fold -w30 | head -n1)
adduser --gecos "" --disabled-password httpuser
echo ""
chpasswd <<< "httpuser:$USER_PASSWORD"
echo ""
echo "Creating principals"
kadmin.local -q "addprinc -randkey HTTP/test-server@$REALM"
echo ""
kadmin.local -q "addprinc -randkey httpuser@$REALM"
echo "Creating keytab files"
kadmin.local -q "ktadd -k ./user.keytab httpuser@$REALM"
echo ""
kadmin.local -q "ktadd -k ./service.keytab HTTP/test-server@$REALM"
echo ""

echo "=================================================================================="
echo "==== Move keytabs somewhere useful ==============================================="
echo "=================================================================================="
echo "Creating keytab directory"
mkdir -p "/tmp/keytabs"
echo ""
echo "Moving keytabs"
mv ./user.keytab /tmp/keytabs
echo ""
mv ./service.keytab /tmp/keytabs
echo ""

echo "=================================================================================="
echo "==== Start krb5 services ========================================================="
echo "=================================================================================="

krb5kdc
kadmind -nofork
