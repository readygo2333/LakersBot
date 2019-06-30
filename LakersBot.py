import random

import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.player import Human
from sc2 import BotAI

import time
import math


class LakersBot(sc2.BotAI):
    def __init__(self, use_model=True):
        self.combinedActions = []
        self.enemy_expand_location = None
        self.first_supply_built=False
        self.cloak_started = False
        self.upgradesIndex = 0        
        #self.stage = "early_rush"
        self.counter_units = {
            MARINE: [SIEGETANK, 3, 1],
            MARAUDER: [MARINE, 3, 3],
            REAPER: [SIEGETANK, 3, 3],
            GHOST: [MARINE, 2, 3],
            SIEGETANK: [BANSHEE, 1, 1],
            BANSHEE: [MARINE, 1, 5]
            }
        self.factory = {
            MARINE: BARRACKS,
            MARAUDER: BARRACKS,
            REAPER: BARRACKS,
            GHOST: GHOSTACADEMY,
            SIEGETANK: FACTORY,
            BANSHEE: STARPORT
        }
        self.army_units = [MARINE, MARAUDER, REAPER, GHOST, SIEGETANK, BANSHEE]
        self.is_defend_rush = False
        self.defend_around = [COMMANDCENTER, SUPPLYDEPOT, SENSORTOWER, MISSILETURRET, BARRACKS, FACTORY]
        self.is_worker_rush = False
        self.attack_round = 0
        self.warmup = 1
        self.Army = []
        self.need_counter_attack = False
        self.engineeringUpgrades = [ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL1,ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL1,
                                    ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL2,ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL2,
                                    ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL3,ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL3]
        self.is_under_attack = False
        self.gogogo = False

    async def on_step(self, iteration):
        #每次迭代前清空，否则有BUG
        self.combinedActions = []
        await self.command_center(iteration)
        await self.tank_sige_handler()
        await self.banshee_visible_handler()
        await self.upgrader()

    async def command_center(self, iteration):
        # 防守
        await self.defend_rush(iteration)
        await self.defend_push()

        # 探测和策略调整
        await self.strategy(iteration)

        ############### 修建筑 ####################
        if self.units(COMMANDCENTER).ready.amount > 3:
            for cc in self.units(COMMANDCENTER).ready:
                await self.adjust_workers(cc)
                await self.build_SUPPLYDEPOT(cc)      # 修建补给站
                await self.build_BARRACKS(cc)         # 修建兵营
                await self.build_REFINERY(cc)         # 修建精炼厂
                await self.build_FACTORY(cc)          # 修建重工厂
                await self.build_STARPORT(cc)         # 修建星港
                await self.build_ENGINEERINGBAY(cc)   # 修建工程站
                await self.build_SENSORTOWER(cc)      # 修建感应塔
                await self.build_MISSILETURRET(cc)    # 修建导弹他
                await self.build_GHOSTACADEMY(cc)     # 修建幽灵学院
                await self.build_BUNKER(cc)           # 修建地堡

        ccs = self.units(COMMANDCENTER).ready
        if ccs.amount == 3:
            cc3 = ccs[2]
            await self.build_SUPPLYDEPOT(cc3)      # 修建补给站
            await self.build_BARRACKS(cc3)         # 修建兵营
            await self.build_REFINERY(cc3)         # 修建精炼厂
            await self.build_FACTORY(cc3)          # 修建重工厂
            await self.build_STARPORT(cc3)         # 修建星港
            await self.build_ENGINEERINGBAY(cc3)   # 修建工程站
            await self.build_SENSORTOWER(cc3)      # 修建感应塔
            await self.build_MISSILETURRET(cc3)    # 修建导弹他
            await self.build_GHOSTACADEMY(cc3)     # 修建幽灵学院
            await self.build_BUNKER(cc3)           # 修建地堡
            await self.adjust_workers(cc3)

        ccs = self.units(COMMANDCENTER).ready
        if ccs.amount == 2:
            cc1 = ccs[0]
            cc2 = ccs[1]
            await self.adjust_workers(cc2)

            await self.build_SENSORTOWER(cc1)      # 修建感应塔
            await self.build_MISSILETURRET(cc1)    # 修建导弹他

            await self.build_SUPPLYDEPOT(cc2)      # 修建补给站
            await self.build_BARRACKS(cc2)         # 修建兵营
            await self.build_REFINERY(cc2)         # 修建精炼厂
            await self.build_FACTORY(cc2)          # 修建重工厂
            await self.build_STARPORT(cc2)         # 修建星港
            await self.build_ENGINEERINGBAY(cc2)   # 修建工程站
            await self.build_SENSORTOWER(cc2)      # 修建感应塔
            await self.build_MISSILETURRET(cc2)    # 修建导弹他

        cc1 = self.units(COMMANDCENTER).ready
        if not cc1.exists:
            await self.worker_rush(iteration)
            return
        else:
            cc1 = cc1.first
            await self.adjust_workers(cc1)

            await self.build_SUPPLYDEPOT(cc1)      # 修建补给站
            await self.build_BARRACKS(cc1)         # 修建兵营
            await self.build_REFINERY(cc1)         # 修建精炼厂
            await self.build_FACTORY(cc1)          # 修建重工厂
            await self.build_STARPORT(cc1)         # 修建星港
            await self.build_ENGINEERINGBAY(cc1)   # 修建工程站

        for cc in self.units(COMMANDCENTER).ready:
            await self.train_WORKERS(cc)           # 训练农民

        ################ 采矿 ######################
        #if not self.is_worker_rush:
        #await self.distribute_workers()
        for a in self.units(REFINERY):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    await self.do(w.random.gather(a))

        #await self.scan_move()

        ############### 扩张 ######################
        await self.expand_command_center(iteration)

    async def army_train(self, unit_type, number):
        if self.units(unit_type).idle.amount < number:
            for st in self.units(self.factory[unit_type]):
                if self.factory[unit_type] == BARRACKS or self.factory[unit_type] == FACTORY or self.factory[unit_type] == STARPORT:
                    if st.add_on_tag != 0 and self.can_afford(unit_type):
                        self.combinedActions.append(st.train(unit_type))
                        if number <= 0:
                            break
                        number = number - 1
                elif self.can_afford(unit_type):
                    self.combinedActions.append(st.train(unit_type))
                    if number <= 0:
                        break
                    number = number - 1
        await self.do_actions(self.combinedActions)

    async def army_attack(self, unit_type, number, target):
        if unit_type == MARINE or unit_type == MARAUDER or unit_type == REAPER or unit_type == GHOST or unit_type == SIEGETANK or unit_type == BANSHEE:
            if self.units(unit_type).idle.amount <= number:
                for u in self.units(unit_type).idle:
                    #self.combinedActions.append(u.stop())
                    self.combinedActions.append(u.attack(target))
            else:
                ug = self.units(unit_type).idle.random_group_of(number)
                for u in ug:
                    #self.combinedActions.append(u.stop())
                    self.combinedActions.append(u.attack(target))
            await self.do_actions(self.combinedActions)

    def my_army(self):
        return self.units(MARINE).ready.amount + self.units(MARAUDER).ready.amount\
            + self.units(REAPER).ready.amount + self.units(SIEGETANK).ready.amount + self.units(BANSHEE).ready.amount

    async def strategy(self, iteration):

        #await self.worker_detect(iteration)
        await self.marine_detect(iteration)

        ################ 训练 ######################
        # 保持至少有5个枪兵
        await self.army_train(MARINE, 5)         # 训练机枪兵

        # 训练枪兵和阿凡达打第一波热身
        # 第一波出去之后暂时不造兵，收集资源扩张一个基地
        if (self.units(COMMANDCENTER).ready.amount == 1 and self.attack_round < self.warmup) or self.units(COMMANDCENTER).ready.amount > 1:
            if self.units(COMMANDCENTER).ready.amount == 1 and self.attack_round < self.warmup:
                await self.army_train(MARINE, 10)         # 训练机枪兵
                await self.army_train(BANSHEE, 2)         # 训练女妖战机

        mr_n = self.known_enemy_units.filter(lambda unit: unit.type_id is MARINE).amount
        bs_n = self.known_enemy_units.filter(lambda unit: unit.type_id is BANSHEE).amount
        md_n = self.known_enemy_units.filter(lambda unit: unit.type_id is MARAUDER).amount
        gs_n = self.known_enemy_units.filter(lambda unit: unit.type_id is GHOST).amount
        st_n = self.known_enemy_units.filter(lambda unit: unit.type_id is SIEGETANK).amount

        if mr_n >= self.counter_units[MARINE][1]:
            await self.army_train(self.counter_units[MARINE][0], self.counter_units[MARINE][2])
        if bs_n >= self.counter_units[BANSHEE][1]:
            await self.army_train(self.counter_units[BANSHEE][0], self.counter_units[BANSHEE][2])
        if md_n >= self.counter_units[MARAUDER][1]:
            await self.army_train(self.counter_units[MARAUDER][0], self.counter_units[MARAUDER][2])
        if gs_n >= self.counter_units[GHOST][1]:
            await self.army_train(self.counter_units[GHOST][0], self.counter_units[GHOST][2])
        if st_n >= self.counter_units[SIEGETANK][1]:
            await self.army_train(self.counter_units[SIEGETANK][0], self.counter_units[SIEGETANK][2])

        ############### 进攻 ###################
        # 第一伦主动进攻：机枪兵大于10个，女妖大于3，进攻
        if self.attack_round < self.warmup:
            if self.units(MARINE).ready.amount >= 10 and self.units(BANSHEE).ready.amount >= 2:
                await self.army_attack(MARINE, 10, self.enemy_start_locations[0])
                await self.army_attack(BANSHEE, 2, self.enemy_start_locations[0])
                self.attack_round += 1
                await self.chat_send("热热身~")

        else:
            # 如果我的军力占优或者相当，派出 80% 军队进攻
            if self.my_army() >= len(self.known_enemy_units) and self.my_army() > 15:
                await self.chat_send("Let's Rock!!!")
                for u in self.army_units:
                    await self.army_attack(u, round(self.units(u).idle.amount * 4 / 5), self.enemy_start_locations[0])

            if self.gogogo == True:
                self.gogogo = False
                await self.chat_send("gogogo!!!")
                for u in self.army_units:
                    await self.army_attack(u, self.units(u).idle.amount, self.enemy_start_locations[0])

    ############ 功能函数 ################
    #把空闲农民派到离指定基地最近的矿上
    async def adjust_workers(self, cc):
        for idle_worker in self.workers.idle:
            mf = self.state.mineral_field.closest_to(cc.position)
            self.combinedActions.append(idle_worker.gather(mf))
        await self.do_actions(self.combinedActions)
        
    async def worker_rush(self, iteration):
        self.actions = []
        target = self.enemy_start_locations[0]
        if iteration == 0:
            await self.chat_send("We will bring you glooooooooooooory!!")
            for worker in self.workers:
                self.actions.append(worker.attack(target))
        await self.do_actions(self.actions)

    async def worker_detect(self, iteration):
        self.actions = []
        target = self.enemy_start_locations[0]
        if iteration != 0 and self.time % 50 == 0:
            for worker in self.workers:
                await self.chat_send("Right away, sir.")
                self.actions.append(worker.attack(target))
                await self.do_actions(self.actions)
                break

    async def marine_detect(self, iteration):
        target = self.enemy_start_locations[0]
        if iteration != 0 and self.time % 50 == 0:
            await self.chat_send("视死如归！！！")
            await self.army_attack(MARINE, 1, target)

    async def train_WORKERS(self, cc):
        for cc in self.units(COMMANDCENTER).ready.noqueue:
            workers = len(self.units(SCV).closer_than(15, cc.position))
            minerals = len(self.state.mineral_field.closer_than(15, cc.position))
            if minerals > 4:
                if workers < 18:
                    if self.can_afford(SCV):
                        await self.do(cc.train(SCV))

    async def build_SUPPLYDEPOT(self, cc):
        if self.supply_left <= 7 and self.can_afford(SUPPLYDEPOT) and not self.already_pending(SUPPLYDEPOT): # and not self.first_supply_built:
            #await self.build(SUPPLYDEPOT, near = cc.position.towards(self.game_info.map_center, 20))
            await self.build(SUPPLYDEPOT, near = self.find_ramp_corner(cc))
            for sd in self.units(SUPPLYDEPOT).ready:
                self.combinedActions.append(sd(MORPH_SUPPLYDEPOT_LOWER))
            await self.do_actions(self.combinedActions)

    async def build_BARRACKS(self, cc):
        if self.units(BARRACKS).amount == 0 and self.can_afford(BARRACKS):
            await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 14, True)) #near = cc.position.towards(self.game_info.map_center, 20))
        if self.units(BARRACKS).amount < self.units(COMMANDCENTER).ready.amount * 2 and self.units(FACTORY).ready.exists and self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
            await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 14, True)) #near = cc.position.towards(self.game_info.map_center, 20))
        #if self.units(BARRACKS).amount < 2 and self.units(STARPORT).ready.exists and self.can_afford(BARRACKS):
        #    await self.build(BARRACKS, near = cc.position.towards(self.game_info.map_center, 20))
        # 修建 FACTORYTECHLAB, 以建掠夺者和幽灵
        for sp in self.units(BARRACKS).ready:
            if sp.add_on_tag == 0:
                await self.do(sp.build(BARRACKSTECHLAB))

    async def build_FACTORY(self, cc):
        if self.units(FACTORY).amount < self.units(COMMANDCENTER).amount and self.units(BARRACKS).ready.exists and self.can_afford(FACTORY) and not self.already_pending(FACTORY):
            #await self.build(FACTORY, near=cc.position.towards(self.game_info.map_center, 12, True))
            await self.build(FACTORY, near=self.main_base_ramp.barracks_correct_placement)
        # 修建 FACTORYTECHLAB, 以建造坦克
        for sp in self.units(FACTORY).ready:
            if sp.add_on_tag == 0:
                await self.do(sp.build(FACTORYTECHLAB))

    async def build_STARPORT(self, cc):
        if self.units(STARPORT).amount < self.units(COMMANDCENTER).amount + 1 and self.units(FACTORY).ready.exists and self.can_afford(STARPORT) and not self.already_pending(STARPORT):
            await self.build(STARPORT, near = cc.position.towards(self.game_info.map_center, 7, True))
        # 修建 STARPORTTECHLAB, 以训练女妖
        for sp in self.units(STARPORT).ready:
            if sp.add_on_tag == 0:
                await self.do(sp.build(STARPORTTECHLAB))

    async def build_ENGINEERINGBAY(self, cc):
        if self.units(ENGINEERINGBAY).amount < 1 and self.can_afford(ENGINEERINGBAY) and not self.already_pending(ENGINEERINGBAY) and self.units(BARRACKS).amount >= 1:
            await self.build(ENGINEERINGBAY, near = cc.position.towards(self.game_info.map_center, 30))

    async def build_SENSORTOWER(self, cc):
        if self.units(SENSORTOWER).amount < 2 * self.units(COMMANDCENTER).amount and self.units(ENGINEERINGBAY).ready.exists and self.can_afford(SENSORTOWER) and not self.already_pending(SENSORTOWER):
            await self.build(SENSORTOWER, near = cc.position.towards(self.game_info.map_center, 2))

    async def build_MISSILETURRET(self, cc):
        if self.units(MISSILETURRET).amount < 2 * self.units(COMMANDCENTER).amount and self.units(SENSORTOWER).ready.exists and self.can_afford(MISSILETURRET) and not self.already_pending(MISSILETURRET):
            await self.build(MISSILETURRET, near = cc.position.towards(self.game_info.map_center, 1))
            await self.build(MISSILETURRET, near=self.find_ramp_corner(cc))

    async def build_GHOSTACADEMY(self, cc):
        if self.units(GHOSTACADEMY).amount < self.units(COMMANDCENTER).amount and self.units(FACTORY).ready.exists and self.can_afford(GHOSTACADEMY) and not self.already_pending(GHOSTACADEMY):
            await self.build(GHOSTACADEMY, near = cc.position.towards(self.game_info.map_center, 20))

    async def build_BUNKER(self, cc):
        if self.units(BUNKER).amount < 2 * self.units(COMMANDCENTER).amount and self.units(GHOSTACADEMY).ready.exists and self.can_afford(BUNKER) and not self.already_pending(BUNKER):
            await self.build(BUNKER, near = cc.position.towards(self.game_info.map_center, 5))

    async def build_REFINERY(self, cc):
        if self.units(BARRACKS).exists and self.units(REFINERY).amount < self.units(COMMANDCENTER).amount * 2 and self.can_afford(REFINERY) and not self.already_pending(REFINERY):
            vgs = self.state.vespene_geyser.closer_than(20.0, cc)
            for vg in vgs:
                if self.units(REFINERY).closer_than(1.0, vg).exists:
                    break
                worker = self.select_build_worker(vg.position)
                if worker is None:
                    break
                await self.do(worker.build(REFINERY, vg))
                break

    def find_ramp_corner(self, cc):
        #self.chat_send(len(self.game_info.map_ramps))
        #ramp = self.game_info.map_ramps[len(self.game_info.map_ramps)-1].corner_depots
        ramp = self.main_base_ramp.corner_depots
        cm = self.units(COMMANDCENTER)
        ramp = {d for d in ramp if cm.closest_distance_to(d) < 20}
        return ramp.pop()

    def get_the_front_cc(self):
        ccs = self.units(COMMANDCENTER)
        return ccs[self.units(COMMANDCENTER).amount - 1]

    async def defend_push(self):
        if self.time >= 5 * 60:
            threats = []
            for structure_type in self.defend_around:
                for structure in self.units(structure_type):
                    threats += self.known_enemy_units.closer_than(30, structure.position)
                    if len(threats) > 0:
                        break
                if len(threats) > 0:
                    break

            if 0 < len(threats) < 7:
                self.is_under_attack = True
                defence_target = threats[0].position.random_on_distance(random.randrange(1, 3))
                await self.army_attack(MARINE, 0, defence_target)
                await self.army_attack(BANSHEE, 0, defence_target)
            elif len(threats) >= 7:
                self.is_under_attack = True
                defence_target = threats[0].position.random_on_distance(random.randrange(1, 3))
                await self.army_attack(MARINE, 0, defence_target)
                await self.army_attack(MARAUDER, 0, defence_target)
                await self.army_attack(REAPER, 0, defence_target)
                await self.army_attack(SIEGETANK, 0, defence_target)
                await self.army_attack(BANSHEE, 0, defence_target)
            elif len(threats) == 0 and self.is_under_attack == True:
                self.is_under_attack = False
                self.gogogo = True


    async def defend_rush(self, iteration):
        # 如果兵力小于15，认为是前期的rush
        if self.time < 5 * 60 and (len(self.units(MARINE)) + len(self.units(REAPER)) + len(self.units(MARAUDER)) < 15 and self.known_enemy_units) or self.is_defend_rush:
            threats = []
            for structure_type in self.defend_around:
                for structure in self.units(structure_type):
                    threats += self.known_enemy_units.closer_than(30, structure.position)
                    if len(threats) > 0:
                        break
                if len(threats) > 0:
                    break

            # 如果有7个及以上的威胁，调动所有农民防守，如果有机枪兵也投入防守
            if len(threats) >= 7:
                self.attack_round += 1
                self.is_defend_rush = True
                self.need_counter_attack = True
                defence_target = threats[0].position.random_on_distance(random.randrange(1, 3))
                for pr in self.units(SCV):
                    self.combinedActions.append(pr.attack(defence_target))
                await self.army_attack(MARINE, round(len(self.units(MARINE)) / 2, defence_target))

            # 如果有2-6个威胁，调动一半农民防守，如果有机枪兵也投入防守
            elif 1 < len(threats) < 7:
                self.attack_round += 1
                self.is_defend_rush = True
                defence_target = threats[0].position.random_on_distance(random.randrange(1, 3))
                self.scv1 = self.units(SCV).random_group_of(round(len(self.units(SCV)) / 2))
                for scv in self.scv1:
                    self.combinedActions.append(scv.attack(defence_target))
                await self.army_attack(MARINE, round(len(self.units(MARINE)) / 2, defence_target))

            # 只有一个威胁，视为骚扰，调动一个农民防守
            elif len(threats) == 1 and not self.is_defend_rush:
                self.is_defend_rush = True
                defence_target = threats[0].position.random_on_distance(random.randrange(1, 3))
                self.scv2 = self.units(SCV).random_group_of(2)
                for scv in self.scv2:
                    self.combinedActions.append(scv.attack(defence_target))

            elif len(threats) == 0 and self.is_defend_rush:
                # 继续采矿
                for worker in self.workers:
                    closest_mineral_patch = self.state.mineral_field.closest_to(worker)
                    self.combinedActions.append(worker.gather(closest_mineral_patch))

                # 小规模防守反击
                if self.need_counter_attack:
                    self.need_counter_attack = False
                    await self.chat_send("Right away, sir!!!")
                    if self.units(MARINE).amount > 5:
                        await self.army_attack(MARINE, 5, self.enemy_start_locations[0])
                    if self.units(BANSHEE).amount > 2:
                        await self.army_attack(BANSHEE, 2, self.enemy_start_locations[0])

                self.is_worker_rush = False
                self.is_defend_rush = False
            await self.do_actions(self.combinedActions)
        else:
            self.is_worker_rush = False
            self.is_defend_rush = False
            # 继续采矿
            for worker in self.workers.idle:
                closest_mineral_patch = self.state.mineral_field.closest_to(worker)
                self.combinedActions.append(worker.gather(closest_mineral_patch))
            await self.do_actions(self.combinedActions)

    async def expand_command_center(self, iteration):
        #if self.units(COMMANDCENTER).exists and (iteration > self.units(COMMANDCENTER).amount * 1500) and self.can_afford(COMMANDCENTER):
        if self.units(COMMANDCENTER).exists and (self.attack_round >= self.warmup or iteration > self.units(COMMANDCENTER).amount * 1500) and self.can_afford(COMMANDCENTER) and not self.already_pending(COMMANDCENTER) and self.units(COMMANDCENTER).amount < 6:
            await self.expand_now()
            #location = await self.get_next_expansion()
            #await self.build(COMMANDCENTER, near=location, max_distance=10, random_alternative=False, placement_step=1)

    async def tank_sige_handler(self):
        # 坦克射程内地面敌人大于3，架坦克，否则恢复正常状态。
        threats = []
        if self.units(SIEGETANK).amount > 0:
            for tank in self.units(SIEGETANK):
                threats += self.known_enemy_units.not_flying.closer_than(15, tank.position)
                if len(threats) > 3:
                    threats.clear()
                    abilities = await self.get_available_abilities(tank)
                    if SIEGEMODE_SIEGEMODE in abilities:
                        self.combinedActions.append(tank(SIEGEMODE_SIEGEMODE))
        if self.units(SIEGETANKSIEGED).amount > 0:
            for sigged_tank in self.units(SIEGETANKSIEGED):
                threats += self.known_enemy_units.not_flying.closer_than(15, sigged_tank.position)
                if len(threats) == 0:
                    abilities = await self.get_available_abilities(sigged_tank)
                    if UNSIEGE_UNSIEGE in abilities:
                        self.combinedActions.append(sigged_tank(UNSIEGE_UNSIEGE))
                else:
                    threats.clear()
        await self.do_actions(self.combinedActions)
            

    async def banshee_visible_handler(self):
        # 周边11(女妖视野)距离内有敌人，且没有导弹塔，隐形，否则恢复正常状态。
        # 能量小于35时不进入隐形（因再次进入隐形会消耗25点能量，35能量可保证隐形15秒左右），能力小于25时候不取消隐形（无法再次立即进入隐形）
        threats = []
        missilet = []
        if self.units(BANSHEE).amount > 0:
            for banshee in self.units(BANSHEE):
                threats += self.known_enemy_units.closer_than(11, banshee.position)
                missilet += self.known_enemy_units.of_type({MISSILETURRET}).closer_than(11, banshee.position)
                if len(threats) > 0 and len(missilet) == 0:
                    threats.clear()
                    abilities = await self.get_available_abilities(banshee)
                    if BEHAVIOR_CLOAKON_BANSHEE in abilities:
                        if banshee.energy > 40:
                            self.combinedActions.append(banshee(BEHAVIOR_CLOAKON_BANSHEE))
                else:
                    threats.clear()
                    abilities = await self.get_available_abilities(banshee)
                    if BEHAVIOR_CLOAKOFF_BANSHEE in abilities:
                        if banshee.energy > 30:
                            self.combinedActions.append(banshee(BEHAVIOR_CLOAKOFF_BANSHEE))
        await self.do_actions(self.combinedActions)
        
    async def upgrader(self):
        if not self.cloak_started and self.units(STARPORTTECHLAB).ready.exists and self.can_afford(RESEARCH_BANSHEECLOAKINGFIELD):
            upgrader = self.units(STARPORTTECHLAB).ready.first
            await self.do(upgrader(RESEARCH_BANSHEECLOAKINGFIELD))
            self.cloak_started = True
            
        #机枪兵按规则只能升1级
        if self.upgradesIndex < 2:
            for EB in self.units(ENGINEERINGBAY).ready.noqueue:
                if self.upgradesIndex < len(self.engineeringUpgrades):
                    if self.can_afford(self.engineeringUpgrades[self.upgradesIndex]):
                        await self.do(EB(self.engineeringUpgrades[self.upgradesIndex]))
                        self.upgradesIndex+=1

    async def scan_move(self):
        #location = self.get_the_front_cc().position.towards(self.game_info.map_center, 25)
        p = await self.get_next_expansion() #self.find_ramp_corner(self.get_the_front_cc())
        location = p.position.towards(self.game_info.map_center, 10)
        for mr in self.units(MARINE):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        for mr in self.units(MARAUDER):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        for mr in self.units(REAPER):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        for mr in self.units(GHOST):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        for mr in self.units(SIEGETANK):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        for mr in self.units(BANSHEE):
            if mr.is_idle:
                #self.combinedActions.append(mr.stop())
                #self.combinedActions.append(mr(SCAN_MOVE, location))
                self.combinedActions.append(mr.move(location))
                self.combinedActions.append(mr.stop())
        await self.do_actions(self.combinedActions)
