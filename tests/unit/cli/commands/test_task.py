# Copyright 2013: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import os.path
import sys

import ddt
import mock
import six

import rally
from rally import api
from rally.cli import cliutils
from rally.cli.commands import task
from rally.common import yamlutils as yaml
from rally import consts
from rally import exceptions
from tests.unit import fakes
from tests.unit import test


@ddt.ddt
class TaskCommandsTestCase(test.TestCase):

    def setUp(self):
        super(TaskCommandsTestCase, self).setUp()
        self.task = task.TaskCommands()
        self.fake_api = fakes.FakeAPI()

        with mock.patch("rally.api.API.check_db_revision"):
            self.real_api = api.API()

    @mock.patch("rally.cli.commands.task.open", create=True)
    def test__load_and_validate_task(self, mock_open):
        input_task = "{'ab': {{test}}}"
        input_args = "{'test': 2}"

        mock_open.side_effect = [
            mock.mock_open(read_data=input_task).return_value,
            mock.mock_open(read_data="{'test': 1}").return_value
        ]
        task_conf = self.task._load_and_validate_task(
            self.real_api, "in_task", args_file="in_args_path")
        self.assertEqual({"ab": 1}, task_conf)

        mock_open.side_effect = [
            mock.mock_open(read_data=input_task).return_value
        ]
        task_conf = self.task._load_and_validate_task(
            self.real_api, "in_task", raw_args=input_args)
        self.assertEqual({"ab": 2}, task_conf)

        mock_open.side_effect = [
            mock.mock_open(read_data=input_task).return_value,
            mock.mock_open(read_data="{'test': 1}").return_value
        ]
        task_conf = self.task._load_and_validate_task(
            self.real_api, "in_task", raw_args=input_args,
            args_file="any_file")
        self.assertEqual({"ab": 2}, task_conf)

        mock_open.side_effect = [
            mock.mock_open(read_data=input_task).return_value,
            mock.mock_open(read_data="{'test': 1}").return_value
        ]
        task_conf = self.task._load_and_validate_task(
            self.real_api, "in_task", raw_args="test=2",
            args_file="any_file")
        self.assertEqual({"ab": 2}, task_conf)

    @mock.patch("rally.cli.commands.task.open", create=True)
    def test__load_task_wrong_task_args_file(self, mock_open):

        def open_return_value(filename):
            if filename == "in_task":
                return mock.Mock()
            else:
                raise IOError()

        mock_open.side_effect = open_return_value

        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task,
                              self.fake_api, task_file="in_task",
                              args_file="in_args_path")
        self.assertEqual("Invalid --task-args-file passed:\n\n\t Error "
                         "reading in_args_path: ", e.format_message())

    @mock.patch("rally.cli.commands.task.yaml.safe_load")
    def test__load_task_wrong_input_task_args(self, mock_safe_load):
        mock_safe_load.side_effect = yaml.ParserError("foo")
        # use real file to avoid mocking open
        task_file = __file__

        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task, self.real_api,
                              task_file, raw_args="{'test': {}")
        self.assertEqual("Invalid --task-args passed:\n\n\t Value has to be "
                         "YAML or JSON. Details:\n\nfoo", e.format_message())
        mock_safe_load.assert_called_once_with("{'test': {}")

        # the case #2
        mock_safe_load.reset_mock()
        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task, self.real_api,
                              task_file, raw_args="[]")
        self.assertEqual("Invalid --task-args passed:\n\n\t Value has to be "
                         "YAML or JSON. Details:\n\nfoo", e.format_message())
        mock_safe_load.assert_called_once_with("[]")

        # the case #3
        mock_safe_load.reset_mock()
        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task, self.real_api,
                              task_file, raw_args="foo")
        self.assertEqual("Invalid --task-args passed:\n\n\t Value has to be "
                         "YAML or JSON. Details:\n\nfoo", e.format_message())
        mock_safe_load.assert_called_once_with("foo")

    @mock.patch("rally.cli.commands.task.open", create=True)
    def test__load_task_task_render_raise_exc(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data="{'test': {{t}}}").return_value
        ]
        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task, self.real_api,
                              "in_task")
        self.assertEqual("Invalid --task passed:\n\n\t Failed to render task "
                         "template.\n\nPlease specify template task argument: "
                         "t", e.format_message())

    @mock.patch("rally.cli.commands.task.yaml")
    @mock.patch("rally.cli.commands.task.open", create=True)
    def test__load_task_task_not_in_yaml(self, mock_open, mock_yaml):
        mock_open.side_effect = [
            mock.mock_open(read_data="{'test': {}").return_value
        ]
        mock_yaml.safe_load.side_effect = Exception("ERROR!!!PANIC!!!")

        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task, self.fake_api,
                              "in_task")
        self.assertEqual("Invalid --task passed:\n\n\t Wrong format of "
                         "rendered input task. It should be YAML or JSON. "
                         "Details:\n\nERROR!!!PANIC!!!", e.format_message())

    def test_load_task_including_other_template(self):
        other_template_path = os.path.join(
            os.path.dirname(rally.__file__), os.pardir,
            "samples/tasks/scenarios/nova/boot.json")
        input_task = "{%% include \"%s\" %%}" % os.path.basename(
            other_template_path)
        expect = self.task._load_and_validate_task(self.real_api,
                                                   other_template_path)

        with mock.patch("rally.cli.commands.task.open",
                        create=True) as mock_open:
            mock_open.side_effect = [
                mock.mock_open(read_data=input_task).return_value
            ]
            input_task_file = os.path.join(
                os.path.dirname(other_template_path), "input_task.json")
            actual = self.task._load_and_validate_task(self.real_api,
                                                       input_task_file)
        self.assertEqual(expect, actual)

    @mock.patch("rally.cli.commands.task.open", create=True)
    def test__load_and_validate_file_failed(self, mock_open):
        mock_open.side_effect = IOError

        e = self.assertRaises(task.FailedToLoadTask,
                              self.task._load_and_validate_task,
                              api=self.fake_api, task_file="some_task",
                              raw_args="task_args", args_file="task_args_file")
        self.assertEqual(
            "Invalid --task passed:\n\n\t Error reading some_task: ",
            e.format_message())

    @mock.patch("rally.cli.commands.task.version")
    @mock.patch("rally.cli.commands.task.TaskCommands.use")
    @mock.patch("rally.cli.commands.task.TaskCommands.detailed")
    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task",
                return_value={"some": "json"})
    def test_start(self, mock__load_and_validate_task, mock_detailed, mock_use,
                   mock_version):
        deployment_id = "e0617de9-77d1-4875-9b49-9d5789e29f20"
        task_path = "path_to_config.json"
        fake_task = fakes.FakeTask(uuid="some_new_uuid", tags=["tag"])
        self.fake_api.task.create.return_value = fake_task
        self.fake_api.task.validate.return_value = fakes.FakeTask(
            some="json", uuid="some_uuid", temporary=True)

        self.task.start(self.fake_api, task_path, deployment_id, do_use=True)
        mock_version.version_string.assert_called_once_with()
        self.fake_api.task.create.assert_called_once_with(
            deployment=deployment_id, tags=None)
        self.fake_api.task.start.assert_called_once_with(
            deployment=deployment_id,
            config=mock__load_and_validate_task.return_value,
            task=fake_task["uuid"],
            abort_on_sla_failure=False)
        mock__load_and_validate_task.assert_called_once_with(
            self.fake_api, task_path, args_file=None, raw_args=None)
        mock_use.assert_called_once_with(self.fake_api, "some_new_uuid")
        mock_detailed.assert_called_once_with(self.fake_api,
                                              task_id=fake_task["uuid"])

    @mock.patch("rally.cli.commands.task.TaskCommands.detailed")
    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task",
                return_value="some_config")
    def test_start_on_unfinished_deployment(self, mock__load_and_validate_task,
                                            mock_detailed):
        deployment_id = "e0617de9-77d1-4875-9b49-9d5789e29f20"
        deployment_name = "xxx_name"
        task_path = "path_to_config.json"
        fake_task = fakes.FakeTask(uuid="some_new_uuid", tag="tag")
        self.fake_api.task.create.return_value = fake_task

        exc = exceptions.DeploymentNotFinishedStatus(
            name=deployment_name,
            uuid=deployment_id,
            status=consts.DeployStatus.DEPLOY_INIT)
        self.fake_api.task.create.side_effect = exc
        self.assertEqual(1, self.task.start(self.fake_api, task_path,
                                            deployment="any",
                                            tags=["some_tag"]))
        self.assertFalse(mock_detailed.called)

    @mock.patch("rally.cli.commands.task.TaskCommands.detailed")
    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task",
                return_value="some_config")
    def test_start_with_task_args(self, mock__load_and_validate_task,
                                  mock_detailed):
        fake_task = fakes.FakeTask(uuid="new_uuid", tags=["some_tag"])
        self.fake_api.task.create.return_value = fakes.FakeTask(
            uuid="new_uuid", tags=["some_tag"])
        self.fake_api.task.validate.return_value = fakes.FakeTask(
            uuid="some_id")

        task_path = "path_to_config.json"
        task_args = "task_args"
        task_args_file = "task_args_file"
        self.task.start(self.fake_api, task_path, deployment="any",
                        task_args=task_args, task_args_file=task_args_file,
                        tags=["some_tag"])

        mock__load_and_validate_task.assert_called_once_with(
            self.fake_api, task_path, raw_args=task_args,
            args_file=task_args_file)

        self.fake_api.task.start.assert_called_once_with(
            deployment="any",
            config=mock__load_and_validate_task.return_value,
            task=fake_task["uuid"],
            abort_on_sla_failure=False)
        mock_detailed.assert_called_once_with(
            self.fake_api,
            task_id=fake_task["uuid"])
        self.fake_api.task.create.assert_called_once_with(
            deployment="any", tags=["some_tag"])

    @mock.patch("rally.cli.commands.task.envutils.get_global")
    def test_start_no_deployment_id(self, mock_get_global):
        mock_get_global.side_effect = exceptions.InvalidArgumentsException
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.task.start, "path_to_config.json", None)

    @mock.patch("rally.cli.commands.task.TaskCommands.detailed")
    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task")
    def test_start_invalid_task(self, mock__load_and_validate_task,
                                mock_detailed):
        task_obj = fakes.FakeTask(temporary=False, tag="tag", uuid="uuid")
        self.fake_api.task.create.return_value = task_obj
        exc = exceptions.InvalidTaskException("foo")

        mock__load_and_validate_task.side_effect = exc

        self.assertRaises(exceptions.InvalidTaskException,
                          self.task.start, self.fake_api, "task_path",
                          "deployment", tags=["tag"])

        self.assertFalse(self.fake_api.task.create.called)
        self.assertFalse(self.fake_api.task.start.called)

        # the case 2
        task_cfg = {"some": "json"}
        mock__load_and_validate_task.side_effect = (task_cfg, )
        self.fake_api.task.start.side_effect = KeyError()

        self.assertRaises(KeyError,
                          self.task.start, self.fake_api, "task_path",
                          "deployment", tags=["tag"])

        self.fake_api.task.create.assert_called_once_with(
            deployment="deployment", tags=["tag"])

        self.fake_api.task.start.assert_called_once_with(
            deployment="deployment", config=task_cfg,
            task=task_obj["uuid"],
            abort_on_sla_failure=False)

        self.assertFalse(mock_detailed.called)

    def test_abort(self):
        test_uuid = "17860c43-2274-498d-8669-448eff7b073f"
        self.task.abort(self.fake_api, test_uuid)
        self.fake_api.task.abort.assert_called_once_with(
            task_uuid=test_uuid, soft=False, async=False)

    @mock.patch("rally.cli.commands.task.envutils.get_global")
    def test_abort_no_task_id(self, mock_get_global):
        mock_get_global.side_effect = exceptions.InvalidArgumentsException
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.task.abort, self.fake_api, None)

    def test_status(self):
        test_uuid = "a3e7cefb-bec2-4802-89f6-410cc31f71af"
        value = {"task_id": "task", "status": "status"}
        self.fake_api.task.get.return_value = value
        self.task.status(self.fake_api, test_uuid)
        self.fake_api.task.get.assert_called_once_with(task_id=test_uuid)

    @mock.patch("rally.cli.commands.task.envutils.get_global")
    def test_status_no_task_id(self, mock_get_global):
        mock_get_global.side_effect = exceptions.InvalidArgumentsException
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.task.status, None)

    @ddt.data({"iterations_data": False, "has_output": True},
              {"iterations_data": True, "has_output": False})
    @ddt.unpack
    def test_detailed(self, iterations_data, has_output):
        test_uuid = "c0d874d4-7195-4fd5-8688-abe82bfad36f"
        detailed_value = {
            "id": "task", "uuid": test_uuid, "status": "finished",
            "subtasks": [{"workloads": [{
                "name": "fake_name", "position": "fake_pos",
                "args": "args", "context": "context", "sla": "sla",
                "runner": "runner", "hooks": [],
                "data": [],
                "statistics": {
                    "durations": {"atomics": [
                        {"name": "foo", "min": 1, "median": 2,
                         "90%ile": 1.5, "95%ile": 1.6, "max": 3,
                         "avg": 1.4, "success": 3, "count": 3},
                        {"name": "bar", "min": 1.1, "median": 2.2,
                         "90%ile": 1.6, "95%ile": 1.65, "max": 3,
                         "avg": 1.5, "success": 3, "count": 3}],
                        "total": {"name": "total", "min": 1, "median": 2.1,
                                  "90%ile": 1.55, "95%ile": 1.62, "max": 3,
                                  "avg": 1.45, "success": 6,
                                  "count": 6}},
                    "atomics": {"foo": {"count": 3}, "bar": {"count": 3}}},
                "load_duration": 3.2,
                "full_duration": 3.5,
                "total_iteration_count": 4,
                "data": [
                    {"duration": 0.9,
                     "idle_duration": 0.1,
                     "output": {"additive": [], "complete": []},
                     "atomic_actions": [{"name": "foo", "started_at": 0.0,
                                         "finished_at": 0.6},
                                        {"name": "bar", "started_at": 0.6,
                                         "finished_at": 1.3}
                                        ],
                     "error": ["type", "message", "traceback"]
                     },
                    {"duration": 1.2,
                     "idle_duration": 0.3,
                     "output": {"additive": [], "complete": []},
                     "atomic_actions": [{"name": "foo", "started_at": 0.0,
                                         "finished_at": 0.6},
                                        {"name": "bar", "started_at": 0.6,
                                         "finished_at": 1.3}
                                        ],
                     "error": ["type", "message", "traceback"]
                     },
                    {"duration": 0.7,
                     "idle_duration": 0.5,
                     "scenario_output": {
                         "data": {"foo": 0.6, "bar": 0.7},
                         "errors": "some"
                     },
                     "atomic_actions": [{"name": "foo", "started_at": 0.0,
                                         "finished_at": 0.6},
                                        {"name": "bar", "started_at": 0.6,
                                         "finished_at": 1.3}
                                        ],
                     "error": ["type", "message", "traceback"]
                     },
                    {"duration": 0.5,
                     "idle_duration": 0.5,
                     "atomic_actions": [{"name": "foo", "started_at": 0.0,
                                         "finished_at": 0.6},
                                        {"name": "bar", "started_at": 0.6,
                                         "finished_at": 1.3}
                                        ],
                     "error": ["type", "message", "traceback"]
                     }],
            }]}]}
        if has_output:
            detailed_value["subtasks"][0]["workloads"][0]["output"] = {
                "additive": [], "complete": []}
        self.fake_api.task.get.return_value = detailed_value
        self.task.detailed(self.fake_api, test_uuid,
                           iterations_data=iterations_data)
        self.fake_api.task.get.assert_called_once_with(
            task_id=test_uuid, detailed=True)

    @mock.patch("rally.cli.commands.task.sys.stdout")
    @mock.patch("rally.cli.commands.task.logging")
    @ddt.data({"debug": True},
              {"debug": False})
    @ddt.unpack
    def test_detailed_task_failed(self, mock_logging, mock_stdout, debug):
        test_uuid = "test_task_id"
        value = {
            "id": "task",
            "uuid": test_uuid,
            "status": consts.TaskStatus.CRASHED,
            "results": [],
            "validation_result": {"etype": "error_type",
                                  "msg": "error_message",
                                  "trace": "error_traceback"}
        }
        self.fake_api.task.get.return_value = value

        mock_logging.is_debug.return_value = debug
        self.task.detailed(self.fake_api, test_uuid)
        if debug:
            expected_calls = [
                mock.call("Task test_task_id: crashed"),
                mock.call("%s" % value["validation_result"]["trace"])]
            mock_stdout.write.assert_has_calls(expected_calls, any_order=True)
        else:
            expected_calls = [
                mock.call("Task test_task_id: crashed"),
                mock.call("%s" % value["validation_result"]["etype"]),
                mock.call("%s" % value["validation_result"]["msg"]),
                mock.call("\nFor more details run:\n"
                          "rally -d task detailed %s" % test_uuid)]
            mock_stdout.write.assert_has_calls(expected_calls, any_order=True)

    @mock.patch("rally.cli.commands.task.sys.stdout")
    def test_detailed_task_status_not_in_finished_abort(self, mock_stdout):
        test_uuid = "test_task_id"
        value = {
            "id": "task",
            "uuid": test_uuid,
            "status": consts.TaskStatus.INIT,
            "results": []
        }
        self.fake_api.task.get.return_value = value
        self.task.detailed(self.fake_api, test_uuid)
        expected_calls = [mock.call("Task test_task_id: init"),
                          mock.call("\nThe task test_task_id marked as "
                                    "'init'. Results available when it "
                                    "is 'finished'.")]
        mock_stdout.write.assert_has_calls(expected_calls, any_order=True)

    @mock.patch("rally.cli.commands.task.envutils.get_global")
    def test_detailed_no_task_id(self, mock_get_global):
        mock_get_global.side_effect = exceptions.InvalidArgumentsException
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.task.detailed, None)

    def test_detailed_wrong_id(self):
        test_uuid = "eb290c30-38d8-4c8f-bbcc-fc8f74b004ae"
        self.fake_api.task.get.return_value = None
        self.task.detailed(self.fake_api, test_uuid)
        self.fake_api.task.get.assert_called_once_with(
            task_id=test_uuid, detailed=True)

    def _make_task(self, status=None, data=None):
        return {
            "status": status or consts.TaskStatus.FINISHED,
            "subtasks": [{"workloads": [{
                "full_duration": 1, "load_duration": 2,
                "created_at": "2016",
                "name": "Foo.bar", "description": "descr",
                "position": 2,
                "args": {"key1": "value1"},
                "runner": {"type": "rruunneerr"},
                "hooks": [],
                "sla": {"failure_rate": {"max": 0}},
                "sla_results": {"sla": [{"success": True}]},
                "context": {"users": {}},
                "data": data or []}]}]}

    @mock.patch("rally.cli.commands.task.json.dumps")
    def test_results(self, mock_json_dumps):
        task_id = "foo_task_id"

        task_obj = self._make_task(data=[{"atomic_actions": {"foo": 1.1}}])
        result = map(lambda x: {"key": {"kw": {"sla": x["sla"],
                                               "args": x["args"],
                                               "context": x["context"],
                                               "runner": x["runner"],
                                               "hooks": x["hooks"]},
                                        "pos": x["position"],
                                        "name": x["name"],
                                        "description": x["description"]},
                                "result": x["data"],
                                "load_duration": x["load_duration"],
                                "full_duration": x["full_duration"],
                                "created_at": x["created_at"],
                                "hooks": x["hooks"],
                                "sla": x["sla_results"]["sla"]},
                     task_obj["subtasks"][0]["workloads"])

        self.fake_api.task.get.return_value = task_obj

        self.assertIsNone(self.task.results(self.fake_api, task_id))
        self.assertEqual(1, mock_json_dumps.call_count)
        self.assertEqual(1, len(mock_json_dumps.call_args[0]))
        self.assertSequenceEqual(result, mock_json_dumps.call_args[0][0])
        self.assertEqual({"sort_keys": False, "indent": 4},
                         mock_json_dumps.call_args[1])
        self.fake_api.task.get.assert_called_once_with(
            task_id=task_id, detailed=True)

    @mock.patch("rally.cli.commands.task.sys.stdout")
    def test_results_no_data(self, mock_stdout):
        task_id = "foo"
        self.fake_api.task.get.return_value = self._make_task(
            status=consts.TaskStatus.CRASHED)

        self.assertEqual(1, self.task.results(self.fake_api, task_id))

        self.fake_api.task.get.assert_called_once_with(
            task_id=task_id, detailed=True)

        expected_out = ("Task status is %s. Results "
                        "available when it is one of %s.") % (
            consts.TaskStatus.CRASHED,
            ", ".join((consts.TaskStatus.FINISHED,
                       consts.TaskStatus.ABORTED)))
        mock_stdout.write.assert_has_calls([mock.call(expected_out)])

    @mock.patch("rally.cli.commands.task.os.path")
    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.plot")
    @mock.patch("rally.cli.commands.task.webbrowser")
    def test_trends(self, mock_webbrowser, mock_plot,
                    mock_open, mock_os_path):
        mock_os_path.exists = lambda p: p.startswith("path_to_")
        mock_os_path.expanduser = lambda p: p + "_expanded"
        mock_os_path.realpath.side_effect = lambda p: "realpath_" + p
        self.task._load_task_results_file = mock.MagicMock(
            return_value=["result_1_from_file", "result_2_from_file"]
        )
        mock_fd = mock.mock_open()
        mock_open.side_effect = mock_fd

        task_obj = self._make_task()
        self.fake_api.task.get.return_value = task_obj
        mock_plot.trends.return_value = "rendered_trends_report"

        ret = self.task.trends(self.fake_api,
                               tasks=["ab123456-38d8-4c8f-bbcc-fc8f74b004ae",
                                      "cd654321-38d8-4c8f-bbcc-fc8f74b004ae",
                                      "path_to_file"],
                               out="output.html", out_format="html")
        expected = [task_obj, task_obj,
                    ["result_1_from_file", "result_2_from_file"]]
        mock_plot.trends.assert_called_once_with(expected)
        self.assertEqual([mock.call(self.fake_api, "path_to_file")],
                         self.task._load_task_results_file.mock_calls)
        self.assertEqual([mock.call("output.html_expanded", "w+")],
                         mock_open.mock_calls)
        self.assertIsNone(ret)
        self.assertFalse(mock_webbrowser.open_new_tab.called)
        mock_fd.return_value.write.assert_called_once_with(
            "rendered_trends_report")

    @mock.patch("rally.cli.commands.task.os.path")
    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.plot")
    @mock.patch("rally.cli.commands.task.webbrowser")
    def test_trends_single_file_and_open_webbrowser(
            self, mock_webbrowser, mock_plot, mock_open, mock_os_path):
        mock_os_path.exists.return_value = True
        mock_os_path.expanduser = lambda path: path
        mock_os_path.realpath.side_effect = lambda p: "realpath_" + p
        self.task._load_task_results_file = mock.MagicMock(
            return_value=["result"]
        )
        ret = self.task.trends(self.real_api,
                               tasks=["path_to_file"], open_it=True,
                               out="output.html", out_format="html")
        self.assertIsNone(ret)
        mock_webbrowser.open_new_tab.assert_called_once_with(
            "file://realpath_output.html")

    @mock.patch("rally.cli.commands.task.os.path")
    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.plot")
    def test_trends_task_id_is_not_uuid_like(self, mock_plot,
                                             mock_open, mock_os_path):
        mock_os_path.exists.return_value = False

        ret = self.task.trends(self.fake_api,
                               tasks=["ab123456-38d8-4c8f-bbcc-fc8f74b004ae"],
                               out="output.html", out_format="html")
        self.assertIsNone(ret)

        ret = self.task.trends(self.fake_api,
                               tasks=["this-is-not-uuid"],
                               out="output.html", out_format="html")
        self.assertEqual(1, ret)

    def test_trends_no_tasks_given(self):
        ret = self.task.trends(self.fake_api, tasks=[],
                               out="output.html", out_format="html")
        self.assertEqual(1, ret)

    @mock.patch("rally.cli.commands.task.os.path.realpath",
                side_effect=lambda p: "realpath_%s" % p)
    @mock.patch("rally.cli.commands.task.open",
                side_effect=mock.mock_open(), create=True)
    @mock.patch("rally.cli.commands.task.plot")
    @mock.patch("rally.cli.commands.task.webbrowser")
    def test_old_report_one_uuid(self, mock_webbrowser,
                                 mock_plot, mock_open, mock_realpath):
        task_id = "eb290c30-38d8-4c8f-bbcc-fc8f74b004ae"
        task_obj = self._make_task()

        self.fake_api.task.get.return_value = task_obj
        mock_plot.plot.return_value = "html_report"

        def reset_mocks():
            for m in (self.fake_api.task.get, mock_webbrowser,
                      mock_plot, mock_open):
                m.reset_mock()
        self.task._old_report(self.fake_api, tasks=task_id,
                              out="/tmp/%s.html" % task_id)
        mock_open.assert_called_once_with("/tmp/%s.html" % task_id, "w+")
        mock_plot.plot.assert_called_once_with([task_obj], include_libs=False)

        mock_open.side_effect().write.assert_called_once_with("html_report")
        self.fake_api.task.get.assert_called_once_with(
            task_id=task_id, detailed=True)

        # JUnit
        reset_mocks()
        self.task._old_report(self.fake_api, tasks=task_id,
                              out="/tmp/%s.html" % task_id,
                              out_format="junit-xml")
        mock_open.assert_called_once_with("/tmp/%s.html" % task_id, "w+")
        self.assertFalse(mock_plot.plot.called)

        # HTML
        reset_mocks()
        self.task._old_report(self.fake_api, task_id, out="output.html",
                              open_it=True, out_format="html")
        mock_webbrowser.open_new_tab.assert_called_once_with(
            "file://realpath_output.html")
        mock_plot.plot.assert_called_once_with([task_obj], include_libs=False)

        # HTML with embedded JS/CSS
        reset_mocks()
        self.task._old_report(self.fake_api, task_id, open_it=False,
                              out="output.html", out_format="html_static")
        self.assertFalse(mock_webbrowser.open_new_tab.called)
        mock_plot.plot.assert_called_once_with([task_obj], include_libs=True)

    @mock.patch("rally.cli.commands.task.os.path.realpath",
                side_effect=lambda p: "realpath_%s" % p)
    @mock.patch("rally.cli.commands.task.open",
                side_effect=mock.mock_open(), create=True)
    @mock.patch("rally.cli.commands.task.plot")
    @mock.patch("rally.cli.commands.task.webbrowser")
    def test_old_report_bunch_uuids(self, mock_webbrowser,
                                    mock_plot, mock_open, mock_realpath):
        tasks = ["eb290c30-38d8-4c8f-bbcc-fc8f74b004ae",
                 "eb290c30-38d8-4c8f-bbcc-fc8f74b004af"]

        task_obj = self._make_task()

        self.fake_api.task.get.return_value = task_obj
        mock_plot.plot.return_value = "html_report"

        def reset_mocks():
            for m in (self.fake_api.task.get, mock_webbrowser,
                      mock_plot, mock_open):
                m.reset_mock()
        self.task._old_report(self.fake_api, tasks=tasks,
                              out="/tmp/1_test.html")
        mock_open.assert_called_once_with("/tmp/1_test.html", "w+")
        mock_plot.plot.assert_called_once_with([task_obj, task_obj],
                                               include_libs=False)

        mock_open.side_effect().write.assert_called_once_with("html_report")
        expected_get_calls = [mock.call(task_id=task, detailed=True)
                              for task in tasks]
        self.fake_api.task.get.assert_has_calls(
            expected_get_calls, any_order=True)

    @mock.patch("rally.cli.commands.task.os.path.exists", return_value=True)
    @mock.patch("rally.cli.commands.task.os.path.realpath",
                side_effect=lambda p: "realpath_%s" % p)
    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.plot")
    def test_old_report_one_file(self, mock_plot, mock_open, mock_realpath,
                                 mock_path_exists):

        task_file = "/tmp/some_file.json"
        task_obj = self._make_task()
        mock_plot.plot.return_value = "html_report"
        mock_open.side_effect = mock.mock_open()
        self.task._load_task_results_file = mock.MagicMock(
            return_value=task_obj
        )

        self.task._old_report(self.real_api, tasks=task_file,
                              out="/tmp/1_test.html")

        self.task._load_task_results_file.assert_called_once_with(
            self.real_api, task_file)
        expected_open_calls = [mock.call("/tmp/1_test.html", "w+")]
        mock_open.assert_has_calls(expected_open_calls, any_order=True)
        mock_plot.plot.assert_called_once_with([task_obj], include_libs=False)
        mock_open.side_effect().write.assert_called_once_with("html_report")

    @mock.patch("rally.cli.commands.task.os.path.exists", return_value=False)
    @mock.patch("rally.cli.commands.task.tutils.open", create=True)
    def test_old_report_exceptions(self, mock_open, mock_path_exists):
        ret = self.task._old_report(self.real_api, tasks="/tmp/task.json",
                                    out="/tmp/tmp.hsml")
        self.assertEqual(1, ret)

    @mock.patch("rally.cli.commands.task.os.path.exists", return_value=True)
    def test_report(self, mock_path_exists):
        self.task._old_report = mock.MagicMock()
        self.task.export = mock.MagicMock()

        self.task.report(self.fake_api, task_id="file",
                         out="out", open_it=False, out_format="html")

        self.task._old_report.assert_called_once_with(
            self.fake_api, tasks="file", out="out", open_it=False,
            out_format="html"
        )

        self.task._old_report.reset_mock()
        self.task.export.reset_mock()
        mock_path_exists.return_value = False

        self.task.report(self.fake_api, task_id="uuid",
                         out="out", open_it=False, out_format="junit-xml")
        self.task.export.assert_called_once_with(
            self.fake_api, task_id="uuid", output_type="junit-xml",
            output_dest="out", open_it=False
        )

    @mock.patch("rally.cli.commands.task.cliutils.print_list")
    @mock.patch("rally.cli.commands.task.envutils.get_global",
                return_value="123456789")
    def test_list(self, mock_get_global, mock_print_list):
        self.fake_api.task.list.return_value = [
            {"uuid": "a",
             "created_at": "2007-01-01T00:00:01",
             "updated_at": "2007-01-01T00:00:03",
             "status": consts.TaskStatus.RUNNING,
             "tags": ["d"],
             "deployment_name": "some_name"}]
        self.task.list(self.fake_api, status="running")
        self.fake_api.task.list.assert_called_once_with(
            deployment=mock_get_global.return_value,
            status=consts.TaskStatus.RUNNING)

        headers = ["UUID", "Deployment name", "Created at", "Load duration",
                   "Status", "Tag(s)"]

        mock_print_list.assert_called_once_with(
            self.fake_api.task.list.return_value, fields=headers,
            normalize_field_names=True,
            sortby_index=headers.index("Created at"),
            formatters=mock.ANY)

    @mock.patch("rally.cli.commands.task.envutils.get_global",
                return_value="123456789")
    def test_list_uuids_only(self, mock_get_global):
        self.fake_api.task.list.return_value = [
            {"uuid": "a",
             "created_at": "2007-01-01T00:00:01",
             "updated_at": "2007-01-01T00:00:03",
             "status": consts.TaskStatus.RUNNING,
             "tags": ["d"],
             "deployment_name": "some_name"}]
        out = six.StringIO()
        with mock.patch.object(sys, "stdout", new=out):
            self.task.list(self.fake_api, status="running", uuids_only=True)
            self.assertEqual("a\n", out.getvalue())
        self.fake_api.task.list.assert_called_once_with(
            deployment=mock_get_global.return_value,
            status=consts.TaskStatus.RUNNING)

    def test_list_wrong_status(self):
        self.assertEqual(1, self.task.list(self.fake_api, deployment="fake",
                                           status="wrong non existing status"))

    def test_list_no_results(self):
        self.fake_api.task.list.return_value = []
        self.assertIsNone(self.task.list(self.fake_api, deployment="fake",
                                         all_deployments=True))
        self.fake_api.task.list.assert_called_once_with()
        self.fake_api.task.list.reset_mock()

        self.assertIsNone(self.task.list(self.fake_api, deployment="d",
                                         status=consts.TaskStatus.RUNNING))
        self.fake_api.task.list.assert_called_once_with(
            deployment="d", status=consts.TaskStatus.RUNNING)

    @mock.patch("rally.cli.commands.task.envutils.get_global",
                return_value="123456789")
    def test_list_output(self, mock_get_global):
        self.fake_api.task.list.return_value = [
            {"uuid": "UUID-1",
             "created_at": "2007-01-01T00:00:01",
             "task_duration": 0.0000009,
             "status": consts.TaskStatus.INIT,
             "tags": [],
             "deployment_name": "some_name"},
            {"uuid": "UUID-2",
             "created_at": "2007-02-01T00:00:01",
             "task_duration": 123.99992,
             "status": consts.TaskStatus.FINISHED,
             "tags": ["tag-1", "tag-2"],
             "deployment_name": "some_name"}]

        # It is a hard task to mock default value of function argument, so we
        # need to apply this workaround
        original_print_list = cliutils.print_list
        print_list_calls = []

        def print_list(*args, **kwargs):
            print_list_calls.append(six.StringIO())
            kwargs["out"] = print_list_calls[-1]
            original_print_list(*args, **kwargs)

        with mock.patch.object(task.cliutils, "print_list",
                               new=print_list):
            self.task.list(self.fake_api, status="running")

        self.assertEqual(1, len(print_list_calls))

        self.assertEqual(
            "+--------+-----------------+---------------------"
            "+---------------+----------+------------------+\n"
            "| UUID   | Deployment name | Created at          "
            "| Load duration | Status   | Tag(s)           |\n"
            "+--------+-----------------+---------------------"
            "+---------------+----------+------------------+\n"
            "| UUID-1 | some_name       | 2007-01-01 00:00:01 "
            "| 0.0           | init     |                  |\n"
            "| UUID-2 | some_name       | 2007-02-01 00:00:01 "
            "| 124.0         | finished | 'tag-1', 'tag-2' |\n"
            "+--------+-----------------+---------------------"
            "+---------------+----------+------------------+\n",
            print_list_calls[0].getvalue())

    def test_delete(self):
        task_uuid = "8dcb9c5e-d60b-4022-8975-b5987c7833f7"
        force = False
        self.task.delete(self.fake_api, task_uuid, force=force)
        self.fake_api.task.delete.assert_called_once_with(
            task_uuid=task_uuid, force=force)

    def test_delete_multiple_uuid(self):
        task_uuids = ["4bf35b06-5916-484f-9547-12dce94902b7",
                      "52cad69d-d3e4-47e1-b445-dec9c5858fe8",
                      "6a3cb11c-ac75-41e7-8ae7-935732bfb48f",
                      "018af931-0e5a-40d5-9d6f-b13f4a3a09fc"]
        force = False
        self.task.delete(self.fake_api, task_uuids, force=force)
        self.assertTrue(
            self.fake_api.task.delete.call_count == len(task_uuids))
        expected_calls = [mock.call(task_uuid=task_uuid,
                                    force=force) for task_uuid in task_uuids]
        self.assertTrue(self.fake_api.task.delete.mock_calls == expected_calls)

    @mock.patch("rally.cli.commands.task.cliutils.print_list")
    def test_sla_check(self, mock_print_list):
        task_obj = self._make_task()
        task_obj["subtasks"][0]["workloads"][0]["sla_results"]["sla"] = [
            {"benchmark": "KeystoneBasic.create_user",
             "criterion": "max_seconds_per_iteration",
             "pos": 0, "success": False, "detail": "Max foo, actually bar"}]

        self.fake_api.task.get.return_value = task_obj
        result = self.task.sla_check(self.fake_api, task_id="fake_task_id")
        self.assertEqual(1, result)
        self.fake_api.task.get.assert_called_with(
            task_id="fake_task_id", detailed=True)

        task_obj["subtasks"][0]["workloads"][0]["sla_results"]["sla"][0][
            "success"] = True

        result = self.task.sla_check(self.fake_api, task_id="fake_task_id",
                                     tojson=True)
        self.assertEqual(0, result)

    @mock.patch("rally.cli.commands.task.os.path.isfile", return_value=True)
    @mock.patch("rally.cli.commands.task.open",
                side_effect=mock.mock_open(read_data="{\"some\": \"json\"}"),
                create=True)
    def test_validate(self, mock_open, mock_os_path_isfile):
        self.fake_api.task.render_template = self.real_api.task.render_template

        self.task.validate(self.fake_api, "path_to_config.json", "fake_id")

        self.fake_api.task.validate.assert_called_once_with(
            deployment="fake_id", config={"some": "json"})

    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task",
                side_effect=task.FailedToLoadTask)
    def test_validate_failed_to_load_task(self, mock__load_and_validate_task):
        args = "args"
        args_file = "args_file"

        mock__load_and_validate_task.side_effect = KeyError("foo")

        self.assertRaises(KeyError, self.task.validate, self.real_api,
                          "path_to_task", "fake_deployment_id",
                          task_args=args, task_args_file=args_file)
        self.assertFalse(self.fake_api.task.validate.called)

        mock__load_and_validate_task.assert_called_once_with(
            self.real_api, "path_to_task", raw_args=args, args_file=args_file)

    @mock.patch("rally.cli.commands.task.TaskCommands._load_and_validate_task")
    def test_validate_invalid(self, mock__load_and_validate_task):
        exc = exceptions.InvalidTaskException("foo")
        self.fake_api.task.validate.side_effect = exc
        self.assertRaises(exceptions.InvalidTaskException,
                          self.task.validate, self.fake_api, "path_to_task",
                          "deployment")
        self.fake_api.task.validate.assert_called_once_with(
            deployment="deployment",
            config=mock__load_and_validate_task.return_value)

    @mock.patch("rally.common.fileutils._rewrite_env_file")
    def test_use(self, mock__rewrite_env_file):
        task_id = "80422553-5774-44bd-98ac-38bd8c7a0feb"
        self.task.use(self.fake_api, task_id)
        mock__rewrite_env_file.assert_called_once_with(
            os.path.expanduser("~/.rally/globals"),
            ["RALLY_TASK=%s\n" % task_id])

    def test_use_not_found(self):
        task_id = "ddc3f8ba-082a-496d-b18f-72cdf5c10a14"
        exc = exceptions.TaskNotFound(uuid=task_id)
        self.fake_api.task.get.side_effect = exc
        self.assertRaises(exceptions.TaskNotFound, self.task.use,
                          self.fake_api, task_id)

    @mock.patch("rally.cli.commands.task.os.path")
    @mock.patch("rally.cli.commands.task.webbrowser.open_new_tab")
    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.print")
    def test_export(self, mock_print, mock_open, mock_open_new_tab,
                    mock_path):

        # file
        self.fake_api.task.export.return_value = {
            "files": {"output_dest": "content"}, "open": "output_dest"}
        mock_path.expanduser.return_value = "output_file"
        mock_path.realpath.return_value = "real_path"
        mock_fd = mock.mock_open()
        mock_open.side_effect = mock_fd

        self.task.export(self.fake_api, task_id="uuid",
                         output_type="json", output_dest="output_dest",
                         open_it=True)

        self.fake_api.task.export.assert_called_once_with(
            tasks_uuids=["uuid"], output_type="json",
            output_dest="output_dest"
        )
        mock_open.assert_called_once_with("output_file", "w+")
        mock_fd.return_value.write.assert_called_once_with("content")

        # print
        self.fake_api.task.export.reset_mock()
        self.fake_api.task.export.return_value = {"print": "content"}
        self.task.export(self.fake_api, task_id="uuid", output_type="json")
        self.fake_api.task.export.assert_called_once_with(
            tasks_uuids=["uuid"], output_type="json", output_dest=None
        )
        mock_print.assert_called_once_with("content")

    @mock.patch("rally.cli.commands.task.plot.charts")
    @mock.patch("rally.cli.commands.task.sys.stdout")
    @ddt.data({"error_type": "test_no_trace_type",
               "error_message": "no_trace_error_message",
               "error_traceback": None,
               },
              {"error_type": "test_error_type",
               "error_message": "test_error_message",
               "error_traceback": "test\nerror\ntraceback",
               })
    @ddt.unpack
    def test_show_task_errors_no_trace(self, mock_stdout,
                                       mock_charts, error_type, error_message,
                                       error_traceback=None):
        mock_charts.MainStatsTable.columns = ["Column 1", "Column 2"]
        test_uuid = "test_task_id"
        error_data = [error_type, error_message]
        if error_traceback:
            error_data.append(error_traceback)
        self.fake_api.task.get.return_value = {
            "id": "task",
            "uuid": test_uuid,
            "status": "finished",
            "subtasks": [{"workloads": [{
                "name": "fake_name",
                "position": "fake_pos",
                "args": {}, "runner": {}, "context": {}, "sla": {},
                "hooks": {},
                "load_duration": 3.2,
                "full_duration": 3.5,
                "statistics": {
                    "durations": {"atomics": [
                        {"name": "foo", "min": 1, "median": 2,
                         "90ile": 1.5, "95ile": 1.6, "max": 3,
                         "average": 1.4, "success": 3, "count": 3},
                        {"name": "bar", "min": 1.1, "median": 2.2,
                         "90ile": 1.6, "95ile": 1.65, "max": 3,
                         "average": 1.5, "success": 3, "count": 3}],
                        "total": {"name": "total", "min": 1, "median": 2.1,
                                  "90ile": 1.55, "95ile": 1.62, "max": 3,
                                  "average": 1.45, "success": 6,
                                  "count": 6}},
                    "atomics": {"foo": {"count": 3}, "bar": {"count": 3}}},
                "total_iteration_count": 1,
                "total_iteration_failed": 1,
                "data": [
                    {"duration": 0.9,
                     "idle_duration": 0.1,
                     "output": {"additive": [], "complete": []},
                     "atomic_actions": {"foo": 0.6, "bar": 0.7},
                     "error": error_data
                     },
                ]},
            ]}],
            "validation_result": json.dumps([error_type, error_message,
                                             error_traceback])
        }
        self.task.detailed(self.fake_api, test_uuid)
        self.fake_api.task.get.assert_called_once_with(
            task_id=test_uuid, detailed=True)
        mock_stdout.write.assert_has_calls([
            mock.call(error_traceback or "No traceback available.")
        ], any_order=False)

    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.yaml.safe_load")
    @mock.patch("rally.cli.commands.task.jsonschema.validate",
                return_value=None)
    def test__load_task_results_file(self, mock_validate, mock_safe_load,
                                     mock_open):
        task_file = "/tmp/task.json"
        workload = {
            "full_duration": 2, "load_duration": 1,
            "created_at": "2017-07-01T07:03:01",
            "updated_at": "2017-07-01T07:03:03",
            "total_iteration_count": 2,
            "failed_iteration_count": 1,
            "min_duration": 3,
            "max_duration": 5,
            "start_time": 1,
            "name": "Foo.bar", "description": "descr",
            "position": 2,
            "args": {"key1": "value1"},
            "runner": {"type": "rruunneerr"},
            "hooks": [{"config": {"type": "hookk"}}],
            "pass_sla": True,
            "sla": {"failure_rate": {"max": 0}},
            "sla_results": {"sla": [{"success": True}]},
            "context": {"users": {}},
            "data": [{"timestamp": 1, "atomic_actions": {"foo": 1.0,
                                                         "bar": 1.0},
                      "duration": 5, "error": [{}]},
                     {"timestamp": 2, "atomic_actions": {"bar": 1.1},
                      "duration": 3, "error": []}],
            "statistics": {"durations": mock.ANY,
                           "atomics": mock.ANY}
        }

        results = [
            {"key": {"name": workload["name"],
                     "description": workload["description"],
                     "pos": workload["position"],
                     "kw": {
                         "args": workload["args"],
                         "runner": workload["runner"],
                         "hooks": [h["config"] for h in workload["hooks"]],
                         "sla": workload["sla"],
                         "context": workload["context"]}},
             "sla": workload["sla_results"]["sla"],
             "result": workload["data"],
             "full_duration": workload["full_duration"],
             "load_duration": workload["load_duration"],
             "created_at": workload["created_at"]}
        ]
        mock_safe_load.return_value = results
        ret = self.task._load_task_results_file(self.fake_api, task_file)
        self.assertEqual({"subtasks": [{"workloads": [workload]}]}, ret)

    @mock.patch("rally.cli.commands.task.open", create=True)
    @mock.patch("rally.cli.commands.task.yaml.safe_load")
    def test__load_task_results_file_wrong_format(self,
                                                  mock_safe_load,
                                                  mock_open):
        task_id = "/tmp/task.json"
        mock_safe_load.return_value = "results"
        self.assertRaises(task.FailedToLoadResults,
                          self.task._load_task_results_file,
                          api=self.real_api, task_id=task_id)

    @mock.patch("rally.cli.commands.task.os.path")
    def test_import_results(self, mock_os_path):
        mock_os_path.exists.return_value = True
        mock_os_path.expanduser = lambda path: path
        self.task._load_task_results_file = mock.MagicMock(
            return_value=["results"]
        )

        self.task.import_results(self.fake_api,
                                 "deployment_uuid",
                                 "task_file", tags=["tag"])

        self.task._load_task_results_file.assert_called_once_with(
            self.fake_api, "task_file"
        )
        self.fake_api.task.import_results.assert_called_once_with(
            deployment="deployment_uuid", task_results=["results"],
            tags=["tag"])

        # not exist
        mock_os_path.exists.return_value = False
        self.assertEqual(
            1,
            self.task.import_results(self.fake_api,
                                     "deployment_uuid",
                                     "task_file", ["tag"])
        )
