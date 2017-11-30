:: This script writes a given public key for a given machine to the public keys file of a given user.
::
:: Arguments
:: 1:   The full content of the public key rsa file.
:: 2:   The name of the machine to which the public key belongs.
:: 3:   The user account that runs the ssh server.
:: 4:   The password for the windows user account and ssh access

set publicKey="%1"
set accessingMachine=%2
set user=%3 
set password=%4

set sshDir="C:/Users/%user%/.ssh"
cd $_sshDir
:: write the content of authorized_keys to keys_temp excluding the public key of the accessing machine
type authorized_keys | findstr /v $_jenkinsMasterContainer >> keys_temp
move /y keys_temp authorized_keys
:: add the new public key to the authorized_keys file
echo %publicKey% >> authorized_keys


:: Update the bitvise server with the new authorized key.
:: With the Bitvise SSH Server the keys in the authorized_keys file are only imported to the server when the windows user logs out. 
:: To force an immediate update, we use the Bitvise SSH Client tool spksc to register the public key with the server.
:: The synchronisation mechanism with the authorized_keys file will make sure that public keys from previous runs 
:: of this script are automatically removed from the servers public key list. This step requires to enter the password again.
set publicKeyFile=%_sshDir%/%accessingMachine%_ssh_key.rsa.pub
echo %publicKey% >> %publicKeyFile%

cd "C:/Program Files (x86)/Bitvise SSH Client"
spksc %user%@buildknechtwin -pw=%4% -unat=n -cmd="Add File %publicKeyFile%"
