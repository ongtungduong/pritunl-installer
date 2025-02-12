from pritunl import utils
from pritunl import logger
from pritunl import settings

import itertools
import subprocess
import time
import threading
import collections
try:
    import iptc
    LIB_IPTABLES = True
except:
    LIB_IPTABLES = False

_global_lock = threading.Lock()

class Iptables(object):
    def __init__(self, server_id, server_type):
        self._tables = {}
        self._routes = set()
        self._routes6 = set()
        self._nat_routes = {}
        self._nat_routes6 = {}
        self._nat_networks = set()
        self._nat_networks6 = set()
        self._deny_routes = set()
        self._deny_routes6 = set()
        name_prefix = '%s_%s'  % (server_id, server_type)
        self._routes_name = name_prefix + 'r'
        self._routes6_name = name_prefix + 'r6'
        self._deny_routes_name = name_prefix + 'd'
        self._deny_routes6_name = name_prefix + 'd6'
        self._nat_routes_name = name_prefix + 'n'
        self._nat_routes6_name = name_prefix + 'n6'
        self._nat_networks_name = name_prefix + 'h'
        self._nat_networks6_name = name_prefix + 'h6'
        self._sets = {}
        self._sets6 = {}
        self._netmaps = {}
        self._accept = []
        self._accept6 = []
        self._drop = []
        self._drop6 = []
        self._deny = []
        self._deny6 = []
        self._other = []
        self._other6 = []
        self._accept_all = False
        self._lock = threading.Lock()
        self.id = None
        self.server_addr = None
        self.server_addr6 = None
        self.virt_interface = None
        self.virt_network = None
        self.virt_network6 = None
        self.ipv6_firewall = None
        self.inter_client = None
        self.ipv6 = False
        self.cleared = False
        self.restrict_routes = False

    def add_route(self, network, nat=False, nat_interface=None):
        if self.cleared:
            return

        if network == '0.0.0.0/0' or network == '::/0':
            self._accept_all = True

        if ':' in network:
            if nat:
                self._nat_routes6[network] = nat_interface
            else:
                self._routes6.add(network)
        else:
            if nat:
                self._nat_routes[network] = nat_interface
            else:
                self._routes.add(network)

    def add_deny_route(self, network):
        if ':' in network:
            self._deny_routes6.add(network)
        else:
            self._deny_routes.add(network)

    def add_nat_network(self, network):
        if self.cleared:
            return

        if ':' in network:
            self._nat_networks6.add(network)
        else:
            self._nat_networks.add(network)

    def add_netmap(self, network, mapping):
        self._netmaps[mapping] = network

    def add_rule(self, rule):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if self.cleared:
                return
            self._other.append(rule)
            if not self._exists_iptables_rule(rule):
                self._insert_iptables_rule(rule)
        finally:
            self._lock.release()

    def add_rule6(self, rule):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if self.cleared:
                return
            self._other6.append(rule)
            if not self._exists_iptables_rule(rule, ipv6=True):
                self._insert_iptables_rule(rule, ipv6=True)
        finally:
            self._lock.release()

    def remove_rule(self, rule, silent=False):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if self.cleared:
                return
            self._other.remove(rule)
            self._remove_iptables_rule(rule)
        except ValueError:
            if not silent:
                logger.warning('Lost iptables rule', 'iptables',
                    rule=rule,
                )
        finally:
            self._lock.release()

    def remove_rule6(self, rule, silent=False):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if self.cleared:
                return
            self._other6.remove(rule)
            self._remove_iptables_rule(rule, ipv6=True)
        except ValueError:
            if not silent:
                logger.warning('Lost ip6tables rule', 'iptables',
                    rule=rule,
                )
        finally:
            self._lock.release()

    def _generate_sets(self):
        routes_set = set()
        routes6_set = set()
        deny_routes_set = set()
        deny_routes6_set = set()
        nat_routes_set = set()
        nat_routes6_set = set()
        nat_networks_set = set()
        nat_networks6_set = set()

        for route in self._routes:
            if route == '0.0.0.0/0':
                continue
            routes_set.add(route)
        for route in self._routes6:
            if route == '::/0':
                continue
            routes6_set.add(route)

        for route in self._deny_routes:
            if route == '0.0.0.0/0':
                continue
            deny_routes_set.add(route)
        for route in self._deny_routes6:
            if route == '::/0':
                continue
            deny_routes6_set.add(route)

        for route in list(self._nat_routes.keys()):
            if route == '0.0.0.0/0':
                continue
            nat_routes_set.add(route)
        for route in list(self._nat_routes6.keys()):
            if route == '::/0':
                continue
            nat_routes6_set.add(route)

        for route in self._nat_networks:
            if route == '0.0.0.0/0':
                continue
            nat_networks_set.add(route)
        for route in self._nat_networks6:
            if route == '::/0':
                continue
            nat_networks6_set.add(route)

        self._sets[self._routes_name] = routes_set
        self._sets6[self._routes6_name] = routes6_set
        self._sets[self._deny_routes_name] = deny_routes_set
        self._sets6[self._deny_routes6_name] = deny_routes6_set
        self._sets[self._nat_routes_name] = nat_routes_set
        self._sets6[self._nat_routes6_name] = nat_routes6_set
        self._sets[self._nat_networks_name] = nat_networks_set
        self._sets6[self._nat_networks6_name] = nat_networks6_set

        self._delete_sets()
        self._create_sets()

    def _generate_input(self):
        if self._accept_all:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.in_interface = self.virt_interface
                rule.create_target('ACCEPT')
                self._accept.append(('INPUT', rule))
            else:
                self._accept.append([
                    'INPUT',
                    '-i', self.virt_interface,
                    '-j', 'ACCEPT',
                ])

            if self.ipv6_firewall:
                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    match = iptc.Match(rule, 'conntrack')
                    match.ctstate = 'RELATED,ESTABLISHED'
                    rule.add_match(match)
                    rule.create_target('ACCEPT')
                    self._accept6.append(('INPUT', rule))
                else:
                    self._accept6.append([
                        'INPUT',
                        '-d', self.virt_network6,
                        '-m', 'conntrack',
                        '--ctstate','RELATED,ESTABLISHED',
                        '-j', 'ACCEPT',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    rule.protocol = 'icmpv6'
                    match = iptc.Match(rule, 'conntrack')
                    match.ctstate = 'NEW'
                    rule.add_match(match)
                    rule.create_target('ACCEPT')
                    self._accept6.append(('INPUT', rule))
                else:
                    self._accept6.append([
                        'INPUT',
                        '-d', self.virt_network6,
                        '-p', 'icmpv6',
                        '-m', 'conntrack',
                        '--ctstate', 'NEW',
                        '-j', 'ACCEPT',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    rule.create_target('DROP')
                    self._drop6.append(('INPUT', rule))
                else:
                    self._drop6.append([
                        'INPUT',
                        '-d', self.virt_network6,
                        '-j', 'DROP',
                    ])
            else:
                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.in_interface = self.virt_interface
                    rule.create_target('ACCEPT')
                    self._accept6.append(('INPUT', rule))
                else:
                    self._accept6.append([
                        'INPUT',
                        '-i', self.virt_interface,
                        '-j', 'ACCEPT',
                    ])

            return

        if self.inter_client:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.in_interface = self.virt_interface
                rule.dst = self.virt_network
                rule.create_target('ACCEPT')
                self._accept.append(('INPUT', rule))
            else:
                self._accept.append([
                    'INPUT',
                    '-i', self.virt_interface,
                    '-d', self.virt_network,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.in_interface = self.virt_interface
                rule.dst = self.virt_network6
                rule.create_target('ACCEPT')
                self._accept6.append(('INPUT', rule))
            else:
                self._accept6.append([
                    'INPUT',
                    '-i', self.virt_interface,
                    '-d', self.virt_network6,
                    '-j', 'ACCEPT',
                ])
        else:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.in_interface = self.virt_interface
                rule.dst = self.server_addr
                rule.create_target('ACCEPT')
                self._accept.append(('INPUT', rule))
            else:
                self._accept.append([
                    'INPUT',
                    '-i', self.virt_interface,
                    '-d', self.server_addr,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.in_interface = self.virt_interface
                rule.dst = self.server_addr6
                rule.create_target('ACCEPT')
                self._accept6.append(('INPUT', rule))
            else:
                self._accept6.append([
                    'INPUT',
                    '-i', self.virt_interface,
                    '-d', self.server_addr6,
                    '-j', 'ACCEPT',
                ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept.append(('INPUT', rule))
        else:
            self._accept.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes_name, 'dst',
                '-j', 'ACCEPT',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes_name, 'dst']
            rule.create_target('DROP')
            self._deny.append(('INPUT', rule))
        else:
            self._deny.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes_name, 'dst',
                '-j', 'DROP',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept.append(('INPUT', rule))
        else:
            self._accept.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes6_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept6.append(('INPUT', rule))
        else:
            self._accept6.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes6_name, 'dst',
                '-j', 'ACCEPT',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes6_name, 'dst']
            rule.create_target('DROP')
            self._deny6.append(('INPUT', rule))
        else:
            self._deny6.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes6_name, 'dst',
                '-j', 'DROP',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes6_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept6.append(('INPUT', rule))
        else:
            self._accept6.append([
                'INPUT',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes6_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop.append(('INPUT', rule))
        else:
            self._drop.append([
                'INPUT',
                '-i', self.virt_interface,
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop6.append(('INPUT', rule))
        else:
            self._drop6.append([
                'INPUT',
                '-i', self.virt_interface,
                '-j', 'DROP',
            ])

    def _generate_output(self):
        if self._accept_all:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.out_interface = self.virt_interface
                rule.create_target('ACCEPT')
                self._accept.append(('OUTPUT', rule))
            else:
                self._accept.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.out_interface = self.virt_interface
                rule.create_target('ACCEPT')
                self._accept6.append(('OUTPUT', rule))
            else:
                self._accept6.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-j', 'ACCEPT',
                ])

            return

        if self.inter_client:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.out_interface = self.virt_interface
                rule.src = self.virt_network
                rule.create_target('ACCEPT')
                self._accept.append(('OUTPUT', rule))
            else:
                self._accept.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-s', self.virt_network,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.out_interface = self.virt_interface
                rule.src = self.virt_network6
                rule.create_target('ACCEPT')
                self._accept6.append(('OUTPUT', rule))
            else:
                self._accept6.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-s', self.virt_network6,
                    '-j', 'ACCEPT',
                ])
        else:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.out_interface = self.virt_interface
                rule.src = self.server_addr
                rule.create_target('ACCEPT')
                self._accept.append(('OUTPUT', rule))
            else:
                self._accept.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-s', self.server_addr,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.out_interface = self.virt_interface
                rule.src = self.server_addr6
                rule.create_target('ACCEPT')
                self._accept6.append(('OUTPUT', rule))
            else:
                self._accept6.append([
                    'OUTPUT',
                    '-o', self.virt_interface,
                    '-s', self.server_addr6,
                    '-j', 'ACCEPT',
                ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes_name, 'src']
            rule.create_target('ACCEPT')
            self._accept.append(('OUTPUT', rule))
        else:
            self._accept.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes_name, 'src',
                '-j', 'ACCEPT',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes_name, 'src']
            rule.create_target('DROP')
            self._deny.append(('OUTPUT', rule))
        else:
            self._deny.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes_name, 'src',
                '-j', 'DROP',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes_name, 'src']
            rule.create_target('ACCEPT')
            self._accept.append(('OUTPUT', rule))
        else:
            self._accept.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes_name, 'src',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes6_name, 'src']
            rule.create_target('ACCEPT')
            self._accept6.append(('OUTPUT', rule))
        else:
            self._accept6.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes6_name, 'src',
                '-j', 'ACCEPT',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes6_name, 'src']
            rule.create_target('DROP')
            self._deny6.append(('OUTPUT', rule))
        else:
            self._deny6.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes6_name, 'src',
                '-j', 'DROP',
            ])
        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes6_name, 'src']
            rule.create_target('ACCEPT')
            self._accept6.append(('OUTPUT', rule))
        else:
            self._accept6.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes6_name, 'src',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop.append(('OUTPUT', rule))
        else:
            self._drop.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop6.append(('OUTPUT', rule))
        else:
            self._drop6.append([
                'OUTPUT',
                '-o', self.virt_interface,
                '-j', 'DROP',
            ])

    def _generate_forward(self):
        if self._accept_all:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.in_interface = self.virt_interface
                rule.create_target('ACCEPT')
                self._accept.append(('FORWARD', rule))
            else:
                self._accept.append([
                    'FORWARD',
                    '-i', self.virt_interface,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.out_interface = self.virt_interface
                rule.create_target('ACCEPT')
                self._accept.append(('FORWARD', rule))
            else:
                self._accept.append([
                    'FORWARD',
                    '-o', self.virt_interface,
                    '-j', 'ACCEPT',
                ])

            if self.ipv6_firewall:
                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    match = iptc.Match(rule, 'conntrack')
                    match.ctstate = 'RELATED,ESTABLISHED'
                    rule.add_match(match)
                    rule.create_target('ACCEPT')
                    self._accept6.append(('FORWARD', rule))
                else:
                    self._accept6.append([
                        'FORWARD',
                        '-d', self.virt_network6,
                        '-m', 'conntrack',
                        '--ctstate', 'RELATED,ESTABLISHED',
                        '-j', 'ACCEPT',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    rule.protocol = 'icmpv6'
                    match = iptc.Match(rule, 'conntrack')
                    match.ctstate = 'NEW'
                    rule.add_match(match)
                    rule.create_target('ACCEPT')
                    self._accept6.append(('FORWARD', rule))
                else:
                    self._accept6.append([
                        'FORWARD',
                        '-d', self.virt_network6,
                        '-p', 'icmpv6',
                        '-m', 'conntrack',
                        '--ctstate', 'NEW',
                        '-j', 'ACCEPT',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    match = iptc.Match(rule, 'conntrack')
                    match.ctstate = 'INVALID'
                    rule.add_match(match)
                    rule.create_target('DROP')
                    self._accept6.append(('FORWARD', rule))
                else:
                    self._accept6.append([
                        'FORWARD',
                        '-d', self.virt_network6,
                        '-m', 'conntrack',
                        '--ctstate', 'INVALID',
                        '-j', 'DROP',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.dst = self.virt_network6
                    rule.create_target('DROP')
                    self._drop6.append(('FORWARD', rule))
                else:
                    self._drop6.append([
                        'FORWARD',
                        '-d', self.virt_network6,
                        '-j', 'DROP',
                    ])
            else:
                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.in_interface = self.virt_interface
                    rule.create_target('ACCEPT')
                    self._accept6.append(('FORWARD', rule))
                else:
                    self._accept6.append([
                        'FORWARD',
                        '-i', self.virt_interface,
                        '-j', 'ACCEPT',
                    ])

                if settings.vpn.lib_iptables and LIB_IPTABLES:
                    rule = self._init_rule6()
                    rule.out_interface = self.virt_interface
                    rule.create_target('ACCEPT')
                    self._accept6.append(('FORWARD', rule))
                else:
                    self._accept6.append([
                        'FORWARD',
                        '-o', self.virt_interface,
                        '-j', 'ACCEPT',
                    ])

            return

        if self.inter_client:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.in_interface = self.virt_interface
                rule.dst = self.virt_network
                rule.create_target('ACCEPT')
                self._accept.append(('FORWARD', rule))
            else:
                self._accept.append([
                    'FORWARD',
                    '-i', self.virt_interface,
                    '-d', self.virt_network,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.in_interface = self.virt_interface
                rule.dst = self.virt_network6
                rule.create_target('ACCEPT')
                self._accept6.append(('FORWARD', rule))
            else:
                self._accept6.append([
                    'FORWARD',
                    '-i', self.virt_interface,
                    '-d', self.virt_network6,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.out_interface = self.virt_interface
                rule.src = self.virt_network
                rule.create_target('ACCEPT')
                self._accept.append(('FORWARD', rule))
            else:
                self._accept.append([
                    'FORWARD',
                    '-o', self.virt_interface,
                    '-s', self.virt_network,
                    '-j', 'ACCEPT',
                ])

            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                rule.out_interface = self.virt_interface
                rule.src = self.virt_network6
                rule.create_target('ACCEPT')
                self._accept6.append(('FORWARD', rule))
            else:
                self._accept6.append([
                    'FORWARD',
                    '-o', self.virt_interface,
                    '-s', self.virt_network6,
                    '-j', 'ACCEPT',
                ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept.append(('FORWARD', rule))
        else:
            self._accept.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes_name, 'src']
            rule.create_target('ACCEPT')
            self._accept.append(('FORWARD', rule))
        else:
            self._accept.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes_name, 'src',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes_name, 'dst']
            rule.create_target('DROP')
            self._deny.append(('FORWARD', rule))
        else:
            self._deny.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes_name, 'dst',
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes_name, 'src']
            rule.create_target('DROP')
            self._deny.append(('FORWARD', rule))
        else:
            self._deny.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes_name, 'src',
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes6_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept6.append(('FORWARD', rule))
        else:
            self._accept6.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes6_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._routes6_name, 'src']
            rule.create_target('ACCEPT')
            self._accept6.append(('FORWARD', rule))
        else:
            self._accept6.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._routes6_name, 'src',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes6_name, 'dst']
            rule.create_target('DROP')
            self._deny6.append(('FORWARD', rule))
        else:
            self._deny6.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes6_name, 'dst',
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._deny_routes6_name, 'src']
            rule.create_target('DROP')
            self._deny6.append(('FORWARD', rule))
        else:
            self._deny6.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._deny_routes6_name, 'src',
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept.append(('FORWARD', rule))
        else:
            self._accept.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes_name, 'src']
            match = iptc.Match(rule, 'conntrack')
            match.ctstate = 'RELATED,ESTABLISHED'
            rule.add_match(match)
            rule.create_target('ACCEPT')
            self._accept.append(('FORWARD', rule))
        else:
            self._accept.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes_name, 'src',
                '-m', 'conntrack',
                '--ctstate', 'RELATED,ESTABLISHED',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes6_name, 'dst']
            rule.create_target('ACCEPT')
            self._accept6.append(('FORWARD', rule))
        else:
            self._accept6.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes6_name, 'dst',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            match = rule.create_match('set')
            match.match_set = [self._nat_routes6_name, 'src']
            match = iptc.Match(rule, 'conntrack')
            match.ctstate = 'RELATED,ESTABLISHED'
            rule.add_match(match)
            rule.create_target('ACCEPT')
            self._accept6.append(('FORWARD', rule))
        else:
            self._accept6.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-m', 'set',
                '--match-set', self._nat_routes6_name, 'src',
                '-m', 'conntrack',
                '--ctstate', 'RELATED,ESTABLISHED',
                '-j', 'ACCEPT',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.in_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop.append(('FORWARD', rule))
        else:
            self._drop.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule()
            rule.out_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop.append(('FORWARD', rule))
        else:
            self._drop.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.in_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop6.append(('FORWARD', rule))
        else:
            self._drop6.append([
                'FORWARD',
                '-i', self.virt_interface,
                '-j', 'DROP',
            ])

        if settings.vpn.lib_iptables and LIB_IPTABLES:
            rule = self._init_rule6()
            rule.out_interface = self.virt_interface
            rule.create_target('DROP')
            self._drop6.append(('FORWARD', rule))
        else:
            self._drop6.append([
                'FORWARD',
                '-o', self.virt_interface,
                '-j', 'DROP',
            ])

    def _generate_pre_routing(self):
        for mapping, network in list(self._netmaps.items()):
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                rule.dst = mapping
                rule.in_interface = self.virt_interface
                tar = rule.create_target('NETMAP')
                tar.to = network
                self._accept.append(('PREROUTING', rule))
            else:
                self._accept.append([
                    'PREROUTING',
                    '-t', 'nat',
                    '-d', mapping,
                    '-i', self.virt_interface,
                    '-j', 'NETMAP',
                    '--to', network,
                ])

    def _generate_post_routing(self):
        all_interface = None
        all_interface6 = None

        cidrs = set()
        cidrs6 = set()
        sorted_routes = collections.defaultdict(list)
        sorted_routes6 = collections.defaultdict(list)
        sorted_nat_routes = collections.defaultdict(list)
        sorted_nat_routes6 = collections.defaultdict(list)

        for route in self._routes:
            cidr = int(route.split('/')[-1])
            cidrs.add(cidr)
            sorted_routes[cidr].append(route)

        for route in self._routes6:
            cidr = int(route.split('/')[-1])
            cidrs6.add(cidr)
            sorted_routes6[cidr].append(route)

        for route, interface in list(self._nat_routes.items()):
            cidr = int(route.split('/')[-1])
            cidrs.add(cidr)
            sorted_nat_routes[cidr].append((route, interface))

        for route, interface in list(self._nat_routes6.items()):
            cidr = int(route.split('/')[-1])
            cidrs6.add(cidr)
            sorted_nat_routes6[cidr].append((route, interface))

        if self._accept_all and all_interface:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule()
                match = rule.create_match('set')
                match.match_set = [self._nat_networks_name, 'src']
                rule.out_interface = all_interface
                rule.create_target('MASQUERADE')
                self._accept.append(('POSTROUTING', rule))
            else:
                self._accept.append([
                    'POSTROUTING',
                    '-t', 'nat',
                    '-m', 'set',
                    '--match-set', self._nat_networks_name, 'src',
                    '-o', all_interface,
                    '-j', 'MASQUERADE',
                ])

        if self._accept_all and all_interface6:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                rule = self._init_rule6()
                match = rule.create_match('set')
                match.match_set = [self._nat_networks6_name, 'src']
                rule.out_interface = all_interface6
                rule.create_target('MASQUERADE')
                self._accept6.append(('POSTROUTING', rule))
            else:
                self._accept6.append([
                    'POSTROUTING',
                    '-t', 'nat',
                    '-m', 'set',
                    '--match-set', self._nat_networks6_name, 'src',
                    '-o', all_interface6,
                    '-j', 'MASQUERADE',
                ])

        for cidr in sorted(cidrs):
            for route, interface in sorted_nat_routes[cidr]:
                for nat_network in self._nat_networks:
                    if settings.vpn.lib_iptables and LIB_IPTABLES:
                        rule = self._init_rule()
                        rule.src = nat_network
                        rule.dst = route
                        if interface:
                            rule.out_interface = interface
                        rule.create_target('MASQUERADE')
                        self._accept.append(('POSTROUTING', rule))
                    else:
                        self._accept.append([
                            'POSTROUTING',
                            '-t', 'nat',
                            '-s', nat_network,
                            '-d', route,
                        ] + (['-o', interface] if interface else []) + [
                            '-j', 'MASQUERADE',
                        ])

            for route in sorted_routes[cidr]:
                for nat_network in self._nat_networks:
                    if settings.vpn.lib_iptables and LIB_IPTABLES:
                        rule = self._init_rule()
                        rule.src = nat_network
                        rule.dst = route
                        rule.create_target('ACCEPT')
                        self._accept.append(('POSTROUTING', rule))
                    else:
                        self._accept.append([
                            'POSTROUTING',
                            '-t', 'nat',
                            '-s', nat_network,
                            '-d', route,
                            '-j', 'ACCEPT',
                        ])

        for cidr in sorted(sorted_nat_routes6.keys()):
            for route, interface in sorted_nat_routes6[cidr]:
                for nat_network in self._nat_networks6:
                    if settings.vpn.lib_iptables and LIB_IPTABLES:
                        rule = self._init_rule6()
                        rule.src = nat_network
                        rule.dst = route
                        if interface:
                            rule.out_interface = interface
                        rule.create_target('MASQUERADE')
                        self._accept6.append(('POSTROUTING', rule))
                    else:
                        self._accept6.append([
                            'POSTROUTING',
                            '-t', 'nat',
                            '-s', nat_network,
                            '-d', route,
                        ] + (['-o', interface] if interface else []) + [
                            '-j', 'MASQUERADE',
                        ])

            for route in sorted_routes6[cidr]:
                for nat_network in self._nat_networks6:
                    if settings.vpn.lib_iptables and LIB_IPTABLES:
                        rule = self._init_rule6()
                        rule.src = nat_network
                        rule.dst = route
                        rule.create_target('ACCEPT')
                        self._accept6.append(('POSTROUTING', rule))
                    else:
                        self._accept6.append([
                            'POSTROUTING',
                            '-t', 'nat',
                            '-s', nat_network,
                            '-d', route,
                            '-j', 'ACCEPT',
                        ])

    def generate(self):
        if self.cleared:
            return

        self._accept = []
        self._accept6 = []
        self._drop = []
        self._drop6 = []
        self._deny = []
        self._deny6 = []

        self._generate_sets()
        self._generate_input()
        self._generate_output()
        self._generate_forward()
        self._generate_pre_routing()
        self._generate_post_routing()

    def _init_rule(self):
        rule = iptc.Rule()
        match = rule.create_match('comment')
        match.comment = 'pritunl-%s' % self.id
        return rule

    def _init_rule6(self):
        rule = iptc.Rule6()
        match = rule.create_match('comment')
        match.comment = 'pritunl-%s' % self.id
        return rule

    def _parse_rule(self, rule):
        return rule + [
            '-m', 'comment',
            '--comment', 'pritunl-%s' % self.id,
        ]

    def _exists_iptables_rule_cmd(self, rule, ipv6=False):
        return False

    def _exists_iptables_rule(self, rule, ipv6=False, tables=None):
        if not isinstance(rule, tuple):
            return self._exists_iptables_rule_cmd(rule, ipv6)

        return False

    def _remove_iptables_rule_cmd(self, rule, ipv6=False):
        rule = self._parse_rule(rule)

        _global_lock.acquire()
        try:
            utils.check_call_silent(
                ['ip6tables' if ipv6 else 'iptables', '-D'] + rule,
            )
            return True
        except subprocess.CalledProcessError:
            return False
        finally:
            _global_lock.release()

    def _remove_iptables_rule(self, rule, ipv6=False, tables=None):
        if not isinstance(rule, tuple):
            return self._remove_iptables_rule_cmd(rule, ipv6)

        _global_lock.acquire()
        try:
            if ipv6:
                if rule[0] == 'POSTROUTING':
                    if tables:
                        table = tables['nat6']
                    else:
                        table = iptc.Table6(iptc.Table.NAT)
                else:
                    if tables:
                        table = tables['filter6']
                    else:
                        table = iptc.Table6(iptc.Table.FILTER)
            else:
                if rule[0] == 'POSTROUTING':
                    if tables:
                        table = tables['nat']
                    else:
                        table = iptc.Table(iptc.Table.NAT)
                else:
                    if tables:
                        table = tables['filter']
                    else:
                        table = iptc.Table(iptc.Table.FILTER)
            chain = iptc.Chain(table, rule[0])
            try:
                chain.delete_rule(rule[1])
            except:
                pass
            return True
        finally:
            _global_lock.release()

    def _insert_iptables_rule_cmd(self, rule, ipv6=False):
        rule = self._parse_rule(rule)

        _global_lock.acquire()
        try:
            for i in range(3):
                try:
                    utils.Process(
                        ['ip6tables' if ipv6 else 'iptables', '-I'] + rule,
                    ).run(15)
                    break
                except:
                    if i == 2:
                        raise
                    logger.error(
                        'Failed to insert iptables rule, retrying...',
                        'iptables',
                        rule=rule,
                    )
                time.sleep(0.5)
        finally:
            _global_lock.release()

    def _insert_iptables_rule(self, rule, ipv6=False, tables=None):
        if not isinstance(rule, tuple):
            return self._insert_iptables_rule_cmd(rule, ipv6)

        _global_lock.acquire()
        try:
            for i in range(3):
                if ipv6:
                    if rule[0] == 'POSTROUTING' or rule[0] == 'PREROUTING':
                        if tables:
                            table = tables['nat6']
                        else:
                            table = iptc.Table6(iptc.Table.NAT)
                    else:
                        if tables:
                            table = tables['filter6']
                        else:
                            table = iptc.Table6(iptc.Table.FILTER)
                else:
                    if rule[0] == 'POSTROUTING' or rule[0] == 'PREROUTING':
                        if tables:
                            table = tables['nat']
                        else:
                            table = iptc.Table(iptc.Table.NAT)
                    else:
                        if tables:
                            table = tables['filter']
                        else:
                            table = iptc.Table(iptc.Table.FILTER)
                chain = iptc.Chain(table, rule[0])
                try:
                    chain.insert_rule(rule[1])
                    break
                except:
                    if i == 2:
                        raise
                    logger.error(
                        'Failed to insert iptables rule, retrying...',
                        'iptables',
                        rule=rule,
                    )
                time.sleep(0.5)
        finally:
            _global_lock.release()

    def _append_iptables_rule_cmd(self, rule, ipv6=False):
        rule = self._parse_rule(rule)

        _global_lock.acquire()
        try:
            for i in range(3):
                try:
                    utils.Process(
                        ['ip6tables' if ipv6 else 'iptables', '-A'] + rule,
                    ).run(15)
                    break
                except:
                    if i == 2:
                        raise
                    logger.error(
                        'Failed to append iptables rule, retrying...',
                        'iptables',
                        rule=rule,
                    )
                time.sleep(0.5)
        finally:
            _global_lock.release()

    def _append_iptables_rule(self, rule, ipv6=False, tables=None):
        if not isinstance(rule, tuple):
            return self._append_iptables_rule_cmd(rule, ipv6)

        _global_lock.acquire()
        try:
            for i in range(3):
                if ipv6:
                    if rule[0] == 'POSTROUTING':
                        if tables:
                            table = tables['nat6']
                        else:
                            table = iptc.Table6(iptc.Table.NAT)
                    else:
                        if tables:
                            table = tables['filter6']
                        else:
                            table = iptc.Table6(iptc.Table.FILTER)
                else:
                    if rule[0] == 'POSTROUTING':
                        if tables:
                            table = tables['nat']
                        else:
                            table = iptc.Table(iptc.Table.NAT)
                    else:
                        if tables:
                            table = tables['filter']
                        else:
                            table = iptc.Table(iptc.Table.FILTER)
                chain = iptc.Chain(table, rule[0])
                try:
                    chain.append_rule(rule[1])
                    break
                except:
                    if i == 2:
                        raise
                    logger.error(
                        'Failed to append iptables rule, retrying...',
                        'iptables',
                        rule=rule,
                    )
                time.sleep(0.5)
        finally:
            _global_lock.release()

    def _create_sets(self, log=False):
        for (name, routes) in self._sets.items():
            utils.check_output_logged(
                ['ipset', 'create', name, 'hash:net', 'family', 'inet'],
            )

            for route in routes:
                utils.check_output_logged(
                    ['ipset', 'add', name, route],
                )

        for (name, routes) in self._sets6.items():
            utils.check_output_logged(
                ['ipset', 'create', name, 'hash:net', 'family', 'inet6'],
            )

            for route in routes:
                utils.check_output_logged(
                    ['ipset', 'add', name, route],
                )

    def _delete_sets(self, log=False):
        for (name, routes) in self._sets.items():
            try:
                utils.check_call_silent(
                    ['ipset', 'destroy', name],
                )
            except subprocess.CalledProcessError:
                return False
        for (name, routes) in self._sets6.items():
            try:
                utils.check_call_silent(
                    ['ipset', 'destroy', name],
                )
            except subprocess.CalledProcessError:
                return False

    def upsert_rules(self, log=False):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                tables = {
                    'nat': iptc.Table(iptc.Table.NAT),
                    'nat6': iptc.Table6(iptc.Table.NAT),
                    'filter': iptc.Table(iptc.Table.FILTER),
                    'filter6': iptc.Table6(iptc.Table.FILTER),
                }
            else:
                tables = None

            # TODO
            # tables['nat'].autocommit = False
            # tables['nat6'].autocommit = False
            # tables['filter'].autocommit = False
            # tables['filter6'].autocommit = False

            if not self._accept:
                return

            for rule in self._accept:
                if not self._exists_iptables_rule(rule, tables=tables):
                    if log:
                        logger.error(
                            'Unexpected loss of iptables rule, ' +
                                'adding again...',
                            'iptables',
                            rule=rule,
                        )
                    self._insert_iptables_rule(rule, tables=tables)

            if self.ipv6:
                for rule in self._accept6:
                    if not self._exists_iptables_rule(rule, ipv6=True,
                            tables=tables):
                        if log:
                            logger.error(
                                'Unexpected loss of ip6tables rule, ' +
                                    'adding again...',
                                'iptables',
                                rule=rule,
                            )
                        self._insert_iptables_rule(rule, ipv6=True,
                            tables=tables)

            if self.restrict_routes:
                for rule in self._drop:
                    if not self._exists_iptables_rule(rule, tables=tables):
                        if log:
                            logger.error(
                                'Unexpected loss of iptables drop rule, ' +
                                    'adding again...',
                                'iptables',
                                rule=rule,
                            )
                        self._append_iptables_rule(rule, tables=tables)

                if self.ipv6:
                    for rule in self._drop6:
                        if not self._exists_iptables_rule(rule, ipv6=True,
                                tables=tables):
                            if log:
                                logger.error(
                                    'Unexpected loss of ip6tables drop ' +
                                        'rule, adding again...',
                                    'iptables',
                                    rule=rule,
                                )
                            self._append_iptables_rule(rule, ipv6=True,
                                tables=tables)

            if self._deny_routes:
                for rule in self._deny:
                    if not self._exists_iptables_rule(rule, tables=tables):
                        if log:
                            logger.error(
                                'Unexpected loss of iptables deny rule, ' +
                                'adding again...',
                                'iptables',
                                rule=rule,
                            )
                        self._insert_iptables_rule(rule, tables=tables)

            if self._deny_routes6 and self.ipv6:
                for rule in self._deny6:
                    if not self._exists_iptables_rule(rule, ipv6=True,
                        tables=tables):
                        if log:
                            logger.error(
                                'Unexpected loss of ip6tables deny ' +
                                'rule, adding again...',
                                'iptables',
                                rule=rule,
                            )
                        self._insert_iptables_rule(rule, ipv6=True,
                            tables=tables)

            # tables['nat'].commit()
            # tables['nat6'].commit()
            # tables['filter'].commit()
            # tables['filter6'].commit()
        finally:
            self._lock.release()

    def clear_rules(self):
        if self.cleared:
            return

        self._lock.acquire()
        try:
            if settings.vpn.lib_iptables and LIB_IPTABLES:
                tables = {
                    'nat': iptc.Table(iptc.Table.NAT),
                    'nat6': iptc.Table6(iptc.Table.NAT),
                    'filter': iptc.Table(iptc.Table.FILTER),
                    'filter6': iptc.Table6(iptc.Table.FILTER),
                }
            else:
                tables = None

            # TODO
            # tables['nat'].autocommit = False
            # tables['nat6'].autocommit = False
            # tables['filter'].autocommit = False
            # tables['filter6'].autocommit = False

            self.cleared = True

            for rule in self._accept + self._other:
                self._remove_iptables_rule(rule, tables=tables)

            if self.ipv6:
                for rule in self._accept6 + self._other6:
                    self._remove_iptables_rule(rule, ipv6=True,
                        tables=tables)

            if self.restrict_routes:
                for rule in self._drop:
                    self._remove_iptables_rule(rule, tables=tables)

                if self.ipv6:
                    for rule in self._drop6:
                        self._remove_iptables_rule(rule, ipv6=True,
                            tables=tables)

            for rule in self._deny:
                self._remove_iptables_rule(rule, tables=tables)

            if self.ipv6:
                for rule in self._deny6:
                    self._remove_iptables_rule(rule, ipv6=True,
                        tables=tables)

            self._delete_sets()

            self._accept = None
            self._accept6 = None
            self._other = None
            self._other6 = None
            self._drop = None
            self._drop6 = None
            self._deny = None
            self._deny6 = None

            # tables['nat'].commit()
            # tables['nat6'].commit()
            # tables['filter'].commit()
            # tables['filter6'].commit()
        finally:
            self._lock.release()

def lock_acquire():
    _global_lock.acquire()

def lock_release():
    _global_lock.release()
