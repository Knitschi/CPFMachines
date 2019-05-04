
Current problems
================

Current Problems
----------------

- Machine names in the config.json files should be given in lower case only, or problems with authenticating ssh server hosts can occur.
- I was not able to make name resolution for windows machines in the host network work inside the docker containers. The machine names for the windows build-slaves
  therefore must be given as ip addresses to allow the jenkins-master to reach them. 

\warning All machines should be within a trusted network as machine to machine communication is currently vulnerable to man in the middle attacks due to
ignoring ssh host key checking.

\warning When the machines access git repositories with the https protocol, the passwords for these
repositories are stored in plain text via the git credential store mechanism on the build slaves and the
jenkins master machine.

Trouble Shooting
----------------

The scripts in the CPFMachines package rely on a rather complex environment that must be setup manually.
A lot can go wrong here so here is a list of the most common problems.

\todo Add list

Notes
-----

- With the current implementation, parallel execution of the build-job is not possible.
  This is because the version of a commit must stay the same while the job is running, because
  the current version number is retrieved multiple times from the repository while the job is running.
  Chaning the number in the meantime would lead to inconsistencies. In the longer run it would be
  good to remove this limitation, which could be a showstopper for highly frequented projects with long
  buildtimes. Another problem is that we do not get a build for each push, which makes it harder to pinpoint
  failed builds to a specific push/developer.

- When using the CPF on Windows, one may be hitting the 260 character limit for filenames. On Windows 10, this
  limit can be switched off. When building on older windows versions, the user can try to reduce the length of his
  configuration names, package names or ci-project name. 

