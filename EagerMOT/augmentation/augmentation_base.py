"""
Abstract parent class for augmenting EagerMOT with other reidentification methods.
Each method should produce a .json file of extended detection results, where each detection has a new element that
represents a feature vector to be used in reidentification.

 The implemented framework allows for comparison between a current detection and an active tracklet, where:
  * the detection has its feature vector as a data member
  * the active tracklet has an array of the feature vectors of all previous detections
    it has been matched with as a data member

 The parent class has the data members:
 * name             =   "Method name"
 * folder           =   "path/to/extended/detection/results"
 * bias_ratio       =   float in range [0, 1] deciding the weight ratio between the EagerMOT affinity matrix and the
                        augmented affinity matrix at concatenation. EagerMOT 1 -------------- 0 Augmented method

 It has two functions that MUST be overridden by a child class:
 * get_features(self, detected_instances, tracks), which is a feature retrieval function
        with in-arguments:
            - detected_instances: a vector of detections (FusedInstances objects)
            - tracks: a vector of tracklets (Track objects)
        that should return:
            - Enumerable vectors of features for the detections and tracklets, each the same length as the in-vectors
 * evaluate_score(self, element_0, element_1), which is score function
        with in-arguments:
            - An element from a detection (typically its feature)
            - An element from a tracklet (typically its feature)
        that should return:
            - A score in [0, 1]U{-1}, where the range [0, 1] has 0 -> perfect match, 1 -> no similarity at all,
                                      and -1 -> this pair is skipped in concatenation, and the original EagerMOT score
                                                for the pair is kept unchanged

Finally, in the same file as the child class definition, but outside the class, there should be a function
create_child_object(method_name: str, automatic_init: bool) which returns an instance of the child class.

This creation should be added to the function create_child_class_object at the end of this file.

"""

from os import path
from json import dump
from abc import ABC, abstractmethod

# Define name macros of implemented augmentation methods in configs/local_parameters.py and import them here
from configs.local_variables import MOUNT_PATH
from augmentation.augmentation_params import VISUAL_SIM_NAME, augmentation_methods, default_settings
import augmentation.augmentation_base_utils as utils_aug


class AugmentationMethod(ABC):
    def __init__(self, method_name: str, automatic_init: bool, eagermot_thresholds: dict):
        self.name = method_name
        self.map_ratio = self.setup_map_ratio(eagermot_thresholds)
        if automatic_init:
            self.folder = default_settings["folder"]
            self.bias_ratio = default_settings["bias ratio"]
        else:
            self.folder = self.get_source_folder_address()
            self.bias_ratio = self.get_bias_ratio_input()

    def get_name(self):
        return self.name

    def get_folder(self):
        return self.folder

    def get_bias_ratio(self):
        return self.bias_ratio

    def get_map_ratio(self, class_target: int):
        return self.map_ratio[class_target]

    def get_source_folder_address(self):
        default_path = MOUNT_PATH + "/Embeddings/" + self.name + "/"
        print("The default folder is " + default_path)
        print("Are your results saved in the default folder? [y/n]")
        savechoice = str(input())
        if savechoice not in ['y', 'Y', 'yes', 'YES', 'Yes', '1', 'default', 'DEFAULT', 'Default']:
            print("Please write the path to your saved results.")
            while True:
                userpath = str(input(MOUNT_PATH))
                custom_folder_addr = MOUNT_PATH + userpath
                if not path.exists(custom_folder_addr):
                    print("Error: folder does not exist. Input again")
                    continue
                # return user chosen folder path
                return custom_folder_addr
        else:
            return default_path

    def get_bias_ratio_input(self):
        headerstring = " EagerMOT"
        for i in range(25 - len(self.name)):
            headerstring += " "
        headerstring += self.name
        print("Insert bias ratio in the range [0, 1]:\n" + headerstring + "\n 1 ----------------------------- 0")
        while True:
            try:
                bias = float(input())
            except ValueError:
                print("Please print a number.")
                continue
            else:
                if 0 <= bias <= 1:
                    return bias
                else:
                    print("Bias ratio outside of permitted range")
                    continue

    @abstractmethod
    def save_augmentation_parameters(self, save_path: str):
        raise NotImplementedError("The child class must override save_augmentation_parameters!")

    @abstractmethod
    def setup_map_ratio(self, eagermot_thresholds: dict):
        raise NotImplementedError("The child class must override setup_map_ratio!")

    @abstractmethod
    def get_features(self, detected_instances, tracks):
        raise NotImplementedError("The child class must override get_features!")

    @abstractmethod
    def evaluate_score(self, element_0, element_1):
        raise NotImplementedError("The child class must override evaluate_score!")


class DoNotAugment(AugmentationMethod):
    """
    Dummy child class for not augmenting EagerMOT.
    Having self.name = DoNotAugment means the augmentation isn't performed.
    """
    def __init__(self, eagermot_thresholds: dict):
        super().__init__('DoNotAugment', True, eagermot_thresholds)

    def setup_map_ratio(self, eagermot_thresholds: dict):
        return eagermot_thresholds

    def save_augmentation_parameters(self, save_path: str):
        params_to_write = {"None": None}
        params_file = path.join(save_path, "No_augmentation_used.json")
        with open(params_file, 'w') as f:
            dump(params_to_write, f, indent=4)

    def get_name(self):
        return False

    def get_features(self, detected_instances, tracks):
        pass

    def evaluate_score(self, element_0, element_1):
        pass


def init_augment(automatic_init: bool, eagermot_thresholds: dict):
    """
    Initiate augmentation, either automatically with the default method, with the user's choice,
    or with the DoNotAugment dummy class if the user declines augmentation.
    """
    if automatic_init:
        default_method_identifier = default_settings['method']
        default_method_name = default_settings['name']
        return create_child_class_object(default_method_identifier, default_method_name, automatic_init,
                                         eagermot_thresholds)
    print("Would you like to augment EagerMOT by concatenating the EagerMOT "
          "affinity matrix with one based on data from another method? [y/n]")
    savechoice = str(input())
    if savechoice in ['y', 'Y', 'yes', 'YES', 'Yes', '1']:
        choice_num = utils_aug.choose_hyper_parameter(augmentation_methods)
        chosen_method_identifier = augmentation_methods[choice_num][2]
        chosen_method_name =  augmentation_methods[choice_num][0]
        return create_child_class_object(chosen_method_identifier, chosen_method_name, automatic_init,
                                         eagermot_thresholds)
    else:
        return DoNotAugment(eagermot_thresholds)


def create_child_class_object(method_identifier: str, name: str, automatic_init: bool, eagermot_thresholds: dict):
    if method_identifier == "vis_sim_2d":
        from augmentation.visual_similarity_2d import create_child_object
    return create_child_object(name, automatic_init, eagermot_thresholds)

