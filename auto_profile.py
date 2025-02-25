import argparse
import json
import os
import shutil
from typing import Dict, Any
from simple_slurm import Slurm


class AutoProfile:
    def __init__(self, config: str = "profiling_settings.json"):
        """Initializes an AutoProfile object

        Args:
            config (str, optional): path to json profiling config file, refer to the example json for the correct format. Defaults to 'profiling_settings.json'.
        """
        self.config = self.load_config(config)
        self.outputs = self.config["files"]["outputs"]
        self.template_dir = self.config["files"]["template_dir"]

    @staticmethod
    def load_config(config_json_file: str) -> Dict[str, Any]:
        """Loads a config file

        Args:
            config_json_file (str): path to json config file

        Returns:
            Dict[str, Any]: _description_
        """
        with open(config_json_file, "r") as f:
            config = json.load(f)
        return config

    def run(self) -> None:
        """Main function for profiling runs"""
        replicates, values = (
            self.config["runs"]["replicates"],
            self.config["runs"]["values"],
        )
        for value in values:
            for replicate in range(1, replicates + 1):
                self.run_replicate(replicate, value)

    def run_replicate(self, replicate, value):
        """Runs one replicate on one value

        Args:
            replicate (int): which replicate number of the run
            value (int): value set in the config file
        """
        template_name = os.path.basename(os.path.normpath(self.template_dir))
        path = os.path.join(
            self.config["files"]["root_dir"],
            f"{template_name}_nstep{value}_r{replicate}",
        )
        shutil.copytree(self.template_dir, path)

        config_file_path = os.path.join(
            path, self.config["files"]["config_file_relative_to_template"]
        )
        search_term = self.config["files"]["config_search_term"]

        self.update_value(value, config_file_path, search_term)
        self.run_slurm(replicate, value, path)

    def update_value(self, value, config_file_path, search_term):
        """Updates a value in a run specific input file

        Args:
            value (int): new value to update to
            config_file_path (str): the script to find
            search_term (str): term to search for within an input file

        Raises:
            FileNotFoundError: if the file does not exist
        """
        if os.path.exists(config_file_path):
            with open(config_file_path, "r+") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if search_term in line:
                        lines[i] = f"{search_term} = {value}\n"

                f.seek(0)
                f.writelines(lines)
                f.truncate()
        else:
            raise FileNotFoundError(f"File {config_file_path} not found")

    def run_slurm(self, replicate, value, path):
        """Creates a slurm object and sbatches it

        Args:
            replicate (int): which replicate the run is on
            value (int): edited value of this specific run
            path (str): path to chdir field

        Raises:
            TypeError: variable missing
            TypeError: command format error
        """
        # runs profile, copies the .prof file over after finishing
        slurm_params = self.config["slurm"]
        slurm_params["job_name"] = f"{value}_{replicate}"
        slurm_params["chdir"] = path

        slurm = Slurm(**slurm_params)

        variables = {
            "profile_name": f"nstep{value}_r{replicate}.prof",
            "script_module": self.config["files"]["script_module_relative_to_template"],
            "input_file": self.config["files"]["input_file_relative_to_template"],
            "output_file": f"nstep{value}_r{replicate}.out",
            "outputs": self.config["files"]["outputs"],
            "working_dir": path,
            "conda_env": self.config["conda_env"],
        }
        print(variables)
        commands = self.config.get("slurm_commands", [])
        print(commands)
        for cmd in commands:
            try:
                formatted_cmd = cmd.format(**variables)
                slurm.add_cmd(formatted_cmd)
            except KeyError as e:
                raise TypeError(f"Warning: Missing variable in command: {e}")
            except Exception as e:
                raise TypeError(f"Error formatting command '{cmd}': {e}")

        print(slurm)
        slurm.sbatch(shell="/bin/bash")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profiling json config file")
    parser.add_argument("config_file", help="Path to json file for automatic profiling")

    args = parser.parse_args()
    auto_profile = AutoProfile(args.config_file)
    auto_profile.run()
