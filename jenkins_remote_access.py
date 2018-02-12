"""
This module provides functionality to execute commands on a jenkins server over its REST API.
"""

import requests
import time


class JenkinsRESTAccessor:
    """
    An objects that holds the data required to access a jenkins server over http and
    that provides functions that execute special commands on that server.
    """
    def __init__(
        self, 
        jenkins_base_url,
        jenkins_user,
        jenkins_user_password
        ):
        self._url = jenkins_base_url
        self._authentication = (jenkins_user,jenkins_user_password)
        self._crumb_request = '{0}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(self._url)
        self._crumb = None


    def wait_until_online(self, max_time):
        """
        Returns when the jenkins instance is fully operable after a restart.
        Fully operable means that the crumb request must work.
        """
        print("----- Wait for jenkins to come online")
        # We have to wait a little or we get python exceptions.
        # This is ugly, because it can still fail on slower machines.
        time.sleep(10)
        crumb_text = "Jenkins-Crumb"

        text = ''
        waited_time = 0
        time_delta = 1
        while crumb_text not in text:
            text = requests.get(self._crumb_request, auth=self._authentication).text
            waited_time += time_delta
            time.sleep(time_delta)
            if waited_time > max_time:
                raise Exception("Timeout while waiting for jenkins to get ready.")
        self._crumb = self._get_jenkins_crumb()


    def approve_system_commands(self, commands):
        """
        This command does the approval operation that can be accessed
        under 'In-process Script Approval' in the jenkins GUI.
        Commands that can be approved with this function are listed there as 'system-commands'
        """
        for command in commands:
            self._approve_jenkins_system_command(command)


    def approve_script_signatures(self, script_signatures):
        """
        This command does the approval operation that can be accessed
        under 'In-process Script Approval' in the jenkins GUI.
        Commands that can be approved with this function are listed there as 'Signatures'
        """
        for script_signature in script_signatures:
            self._approve_jenkins_script_signature(script_signature)


    def _get_jenkins_crumb(self):
        request = requests.get(self._crumb_request, auth=self._authentication)
        request.raise_for_status()
        return request.text


    def _approve_jenkins_system_command(self, command):
        """
        Runs a groovy script over the jenkins groovy console, that approves system-command
        scipts.
        """
        groovy_script = (
            "def scriptApproval = Jenkins.instance.getExtensionList('org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval')[0];" +
            "scriptApproval.approveScript(scriptApproval.hash('{0}', 'system-command'))"
            ).format(command)
        self._run_jenkins_groovy_script(groovy_script)


    def _run_jenkins_groovy_script(self, script):
        """
        Runs the given script in the jenkins script console.
        """
        url = '{0}/scriptText'.format(self._url)
        crumb_parts = self._crumb.split(':')
        crumb_header = {crumb_parts[0] : crumb_parts[1]}
        script_data = {'script' : script}

        response = requests.post(url, auth=self._authentication, headers=crumb_header, data=script_data)
        response.raise_for_status()


    def _approve_jenkins_script_signature(self, script_signature):
        """
        Runs a groovy script over the jenkins groovy console, that approves the commands
        that are used to start the slaves.
        """
        groovy_script = (
            "def signature = '{0}';" +
            "org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval.get().approveSignature(signature)"
        ).format(script_signature)
        self._run_jenkins_groovy_script(groovy_script)
    