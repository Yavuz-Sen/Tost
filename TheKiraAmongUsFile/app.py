import random
import time

# ==============================================================================
# 1. ROL TANIMLARI
# ==============================================================================
ROLES = {
    'KIRA': {
        'id': 'KIRA',
        'name': 'Kira (Light)',
        'team': 'KIRA',
        'goal': 'Soruşturma ekibini tek tek eleyerek üstünlük kurmak.',
        'ability': 'Her gece Death Note\'a bir kurban ismi yazar (Kalp krizi).'
    },
    'MISA': {
        'id': 'MISA',
        'name': 'Misa / İkinci Kira',
        'team': 'KIRA',
        'goal': 'Kira\'ya yardım etmek ve soruşturmacıları şaşırtmak.',
        'ability': 'Şinigami Gözleri ile oyunda en fazla 2 kez birinin TAM rolünü öğrenir.'
    },
    'L': {
        'id': 'L',
        'name': 'L (Lider Dedektif)',
        'team': 'TOWN',
        'goal': 'Kira ve Misa\'yı tespit edip gündüz idam ettirmek.',
        'ability': 'Her gece bir oyuncuyu sorgular: "Kira Tarafı" mı yoksa "Masum" mu öğrenir.'
    },
    'WATARI': {
        'id': 'WATARI',
        'name': 'Watari (Koruyucu)',
        'team': 'TOWN',
        'goal': 'Masumları ve L\'i Kira\'nın defterinden korumak.',
        'ability': 'Her gece bir oyuncuyu korumaya alır. O gece yazılırsa hedef ölmez.'
    },
    'CITIZEN': {
        'id': 'CITIZEN',
        'name': 'Soruşturma Ekibi (Near/Mello)',
        'team': 'TOWN',
        'goal': 'Gündüz tartışmalarında mantık yürüterek Kira\'yı bulmak.',
        'ability': 'Özel gece gücü yoktur, oylamada yüksek analiz gücüne sahiptir.'
    },
    'RYUK': {
        'id': 'RYUK',
        'name': 'Ryuk (Şinigami)',
        'team': 'NEUTRAL',
        'goal': 'Eğlenmek! Tek amacı gündüz mahkemesinde kendisini astırmaktır.',
        'ability': 'Gündüz oylamasında asılırsa oyunu anında TEK BAŞINA kazanır.'
    }
}

BOT_NAMES = [
    'L Lawliet', 'Light Yagami', 'Misa Amane', 'Near (N)', 'Mello (M)', 
    'Watari', 'Matsuda', 'Aizawa', 'Mogi', 'Ide', 'Teru Mikami'
]

# ==============================================================================
# 2. OYUNCU SINIFI
# ==============================================================================
class Player:
    def __init__(self, player_id, name, is_ai, role):
        self.id = player_id
        self.name = name
        self.is_ai = is_ai
        self.role = role
        self.is_alive = True

    def __repr__(self):
        status = "CANLI" if self.is_alive else "ÖLÜ"
        return f"{self.name} ({self.role['name']}) - {status}"

# ==============================================================================
# 3. OYUN MOTORU
# ==============================================================================
class DeathNoteGame:
    def __init__(self):
        self.mode = 'ai'  # 'ai' veya 'pass'
        self.players = []
        self.night_number = 1
        self.misa_charges_left = 2
        self.game_over = False

    def setup_game(self):
        print("="*60)
        print("         DEATH NOTE: KASABADAKİ DEFTER (Python)")
        print("="*60)
        
        # Oyun Modu Seçimi
        print("\n1- Yapay Zeka BOTS (Tek Başına Oyna)")
        print("2- Pass & Play (Aynı Cihazda Sırayla Oyna)")
        mode_choice = input("Mod Seçiniz (1/2, Varsayılan: 1): ").strip()
        self.mode = 'pass' if mode_choice == '2' else 'ai'

        names_data = []

        if self.mode == 'ai':
            human_name = input("\nAdınızı Girin (Varsayılan: Kira Hunter): ").strip() or "Kira Hunter"
            
            print("\nTercih Edilen Rol Seçin:")
            print("1. RANDOM (Rastgele)")
            print("2. KIRA")
            print("3. L")
            print("4. MISA")
            print("5. WATARI")
            print("6. RYUK")
            print("7. CITIZEN")
            role_map = {'1':'RANDOM', '2':'KIRA', '3':'L', '4':'MISA', '5':'WATARI', '6':'RYUK', '7':'CITIZEN'}
            role_choice = input("Seçiminiz (1-7): ").strip()
            preferred_role = role_map.get(role_choice, 'RANDOM')

            try:
                count = int(input("\nToplam Oyuncu Sayısı (6-10 arası, Varsayılan: 7): "))
                count = max(6, min(10, count))
            except ValueError:
                count = 7

            names_data.append({'name': human_name, 'is_ai': False, 'preferred_role': preferred_role})

            shuffled_bots = [b for b in BOT_NAMES if b != human_name]
            random.shuffle(shuffled_bots)

            for i in range(count - 1):
                bot_name = shuffled_bots[i] if i < len(shuffled_bots) else f"Dedektif #{i+1}"
                names_data.append({'name': bot_name, 'is_ai': True, 'preferred_role': 'RANDOM'})
        else:
            print("\nOyuncu İsimlerini Girin (En az 6 oyuncu, bitirmek için boş satıra Enter basın):")
            idx = 1
            while True:
                p_name = input(f"{idx}. Oyuncu Adı: ").strip()
                if not p_name:
                    if len(names_data) >= 6:
                        break
                    else:
                        print(f"En az 6 oyuncu girmelisiniz! (Şu an: {len(names_data)})")
                        continue
                names_data.append({'name': p_name, 'is_ai': False, 'preferred_role': 'RANDOM'})
                idx += 1

        # Rol Destesi Oluşturma ve Dağıtma
        roles_list = self.build_role_deck(len(names_data), names_data[0].get('preferred_role', 'RANDOM'))
        
        for idx, item in enumerate(names_data):
            player = Player(
                player_id=f"player_{idx}",
                name=item['name'],
                is_ai=item['is_ai'],
                role=roles_list[idx]
            )
            self.players.append(player)

        print("\n[!] Oyun Başladı! Kasabada gerilim tırmanıyor...\n")

    def build_role_deck(self, count, preferred_role):
        deck = [ROLES['KIRA'], ROLES['L'], ROLES['WATARI'], ROLES['MISA'], ROLES['RYUK']]
        while len(deck) < count:
            deck.append(ROLES['CITIZEN'])

        random.shuffle(deck)

        if preferred_role != 'RANDOM':
            found_idx = next((i for i, r in enumerate(deck) if r['id'] == preferred_role), None)
            if found_idx is not None:
                deck[0], deck[found_idx] = deck[found_idx], deck[0]
        return deck

    # ==========================================================================
    # 4. GECE EVRESİ
    # ==========================================================================
    def start_night_phase(self):
        print(f"\n=================== GECE {self.night_number} BAŞLADI ===================")
        print("Karanlık çöktü. Tüm kasaba uykuya çekildi...\n")

        night_actions = {
            'kira_target': None,
            'watari_target': None,
            'l_target': None,
            'misa_target': None
        }

        if self.mode == 'pass':
            for player in self.players:
                if not player.is_alive:
                    continue
                input(f"\n[Ekrana Sadece '{player.name}' Baksın!] Devam etmek için Enter'a basın...")
                self.process_player_night_turn(player, night_actions)
                print("\n" * 30) # Ekranı temizleme efekti
        else:
            # AI Modunda
            human_player = self.players[0]

            # Bot Eylemleri
            alive_players = [p for p in self.players if p.is_alive]
            for p in self.players:
                if p.is_ai and p.is_alive:
                    targets = [t for t in alive_players if t.id != p.id]
                    if not targets:
                        continue
                    random_target = random.choice(targets)

                    if p.role['id'] == 'KIRA':
                        night_actions['kira_target'] = random_target.id
                    elif p.role['id'] == 'WATARI':
                        night_actions['watari_target'] = random_target.id
                    elif p.role['id'] == 'L':
                        night_actions['l_target'] = random_target.id
                    elif p.role['id'] == 'MISA' and self.misa_charges_left > 0:
                        night_actions['misa_target'] = random_target.id

            # İnsan Eylemi
            if human_player.is_alive:
                self.process_player_night_turn(human_player, night_actions)
            else:
                print("Siz öldüğünüz için geceyi izliyorsunuz...")
                time.sleep(1)

        self.resolve_night_results(night_actions)

    def process_player_night_turn(self, player, night_actions):
        print(f"\n--- Sıra Sizde: {player.name} ---")
        print(f"Rolünüz: {player.role['name']} | Taraf: {player.role['team']}")
        print(f"Yetenek: {player.role['ability']}")

        alive_targets = [p for p in self.players if p.is_alive and p.id != player.id]

        if player.role['id'] == 'KIRA':
            target = self.prompt_player_selection("Death Note'a yazıp öldürmek istediğiniz oyuncuyu seçin:", alive_targets)
            if target:
                night_actions['kira_target'] = target.id

        elif player.role['id'] == 'WATARI':
            # Watari kendisini de koruyabilir
            all_alive = [p for p in self.players if p.is_alive]
            target = self.prompt_player_selection("Korumak istediğiniz oyuncuyu seçin:", all_alive)
            if target:
                night_actions['watari_target'] = target.id

        elif player.role['id'] == 'L':
            target = self.prompt_player_selection("Sorgulamak (şüpheli tespiti yapımı) istediğiniz oyuncuyu seçin:", alive_targets)
            if target:
                night_actions['l_target'] = target.id
                is_evil = target.role['team'] == 'KIRA'
                result = "🔴 KIRA TARAFI!" if is_evil else "🟢 MASUM"
                print(f"\n🔍 [L Soruşturma Sonucu]: {target.name} -> {result}")
                input("Devam etmek için Enter'a basın...")

        elif player.role['id'] == 'MISA':
            if self.misa_charges_left > 0:
                print(f"Kalan Şinigami Gözü Hakkı: {self.misa_charges_left}")
                choice = input("Göz hakkı kullanmak ister misiniz? (E/H): ").strip().lower()
                if choice == 'e':
                    target = self.prompt_player_selection("TAM rolünü öğrenmek istediğiniz oyuncuyu seçin:", alive_targets)
                    if target:
                        night_actions['misa_target'] = target.id
                        self.misa_charges_left -= 1
                        print(f"\n👁️ [Şinigami Gözleri]: {target.name} oyuncusunun GERÇEK rolü: {target.role['name']}")
                        input("Devam etmek için Enter'a basın...")
            else:
                print("Göz hakkınız kalmadı. Gece pas geçiliyor.")
                input("Devam etmek için Enter'a basın...")
        else:
            print("Gece yapacak özel bir eyleminiz bulunmuyor.")
            input("Geceyi geçmek için Enter'a basın...")

    def prompt_player_selection(self, prompt_text, valid_players):
        print(f"\n{prompt_text}")
        for idx, p in enumerate(valid_players, 1):
            print(f"{idx}. {p.name}")
        
        while True:
            try:
                choice = int(input("Seçiminiz (Numara): "))
                if 1 <= choice <= len(valid_players):
                    return valid_players[choice - 1]
            except ValueError:
                pass
            print("Geçersiz seçim, lütfen listedeki numaralardan birini girin.")

    def resolve_night_results(self, night_actions):
        kira_target = night_actions['kira_target']
        watari_target = night_actions['watari_target']

        killed_player = None
        if kira_target and kira_target != watari_target:
            killed_player = next((p for p in self.players if p.id == kira_target), None)

        self.start_day_phase(killed_player)

    # ==========================================================================
    # 5. GÜNDÜZ VE OYLAMA EVRESİ
    # ==========================================================================
    def start_day_phase(self, killed_player):
        print(f"\n=================== GÜNDÜZ {self.night_number} BAŞLADI ===================")
        print("Güneş doğdu. Kasaba meydanında toplanılıyor...\n")

        if killed_player:
            killed_player.is_alive = False
            print(f"💀 SOHBET MEYDANI: {killed_player.name} yatağında ölü bulundu! Death Note Ölüm Sebebi: Kalp Krizi.")
        else:
            print("🛡️ Bu gece kimse ölmedi! Watari doğru kişiyi korumuş olabilir.")

        if self.check_win_conditions():
            return

        print("\n--- GÜNDÜZ TARTIŞMASI VE MAHKEME ---")
        alive_players = [p for p in self.players if p.is_alive]
        print("Canlı Oyuncular:")
        for p in alive_players:
            print(f"- {p.name}")

        input("\nDisküsyon tamamlandı. Mahkeme oylamasına geçmek için Enter'a basın...")
        self.process_voting_phase()

    def process_voting_phase(self):
        print("\n=================== MAHKEME OYLAMASI ===================")
        print("Kira olduğundan şüphelendiğiniz kişiyi oylayarak mahkemede asın!\n")

        alive_players = [p for p in self.players if p.is_alive]
        votes = {p.id: 0 for p in alive_players}

        if self.mode == 'pass':
            for player in alive_players:
                input(f"\n[Ekrana Sadece '{player.name}' Baksın!] Oy vermek için Enter'a basın...")
                valid_targets = [p for p in alive_players if p.id != player.id]
                target = self.prompt_player_selection(f"{player.name}, idam edilmesini istediğin kişiyi seç:", valid_targets)
                votes[target.id] += 1
                print("\n" * 30)
        else:
            # AI Modu Oylaması
            human = self.players[0]
            if human.is_alive:
                valid_targets = [p for p in alive_players if p.id != human.id]
                target = self.prompt_player_selection("İdam edilmesini istediğiniz oyuncuyu seçin:", valid_targets)
                votes[target.id] += 1

            # Bot Oyları
            for p in alive_players:
                if p.is_ai:
                    possible_targets = [t for t in alive_players if t.id != p.id]
                    if possible_targets:
                        bot_choice = random.choice(possible_targets)
                        votes[bot_choice.id] += 1

        # En çok oy kalanı bulma
        max_votes = 0
        lynched_id = None
        tie = False

        for pid, count in votes.items():
            if count > max_votes:
                max_votes = count
                lynched_id = pid
                tie = False
            elif count == max_votes and max_votes > 0:
                tie = True

        if lynched_id and not tie:
            lynched = next(p for p in self.players if p.id == lynched_id)
            lynched.is_alive = False
            print(f"\n⚖️️ MAHKEME KARARI: {lynched.name} çoğunluk oyuyla ({max_votes} oy) idam edildi!")
            print(f"📜 {lynched.name} oyuncusunun gerçek rolü: {lynched.role['name']}")

            # RYUK KAZANMA KONTROLÜ
            if lynched.role['id'] == 'RYUK':
                self.trigger_end_game('RYUK', 'Ryuk kendisini astırmayı başardı ve elmasından bir ısırık alarak oyunu TEK BAŞINA kazandı!')
                return
        else:
            print("\n⚖️ Oylar eşit çıktı veya oy kullanılmadı, bugün kimse idam edilmedi.")

        if not self.check_win_conditions():
            self.night_number += 1
            input("\nGeceye geçmek için Enter'a basın...")
            self.start_night_phase()

    # ==========================================================================
    # 6. KAZANMA KOŞULLARI
    # ==========================================================================
    def check_win_conditions(self):
        alive = [p for p in self.players if p.is_alive]
        kira_team = [p for p in alive if p.role['team'] == 'KIRA']
        town_team = [p for p in alive if p.role['team'] in ['TOWN', 'NEUTRAL']]

        # 1. Soruşturma Ekibi Kazandı
        if len(kira_team) == 0:
            self.trigger_end_game('TOWN', 'Tüm Kira destekçileri ve Light Yagami etkisiz hale getirildi. Adalet sağlandı!')
            return True

        # 2. Kira Tarafı Kazandı
        if len(kira_team) >= len(town_team):
            self.trigger_end_game('KIRA', 'Kira kasabada tam kontrolü sağladı. Yeni Dünya\'nın Tanrısı doğdu!')
            return True

        return False

    def trigger_end_game(self, winner_team, description):
        self.game_over = True
        print("\n" + "="*60)
        if winner_team == 'TOWN':
            print("🏆 ADALET KAZANDI (SORUŞTURMA EKİBİ)")
        elif winner_team == 'KIRA':
            print("💀 KIRA KAZANDI!")
        else:
            print("🍎 RYUK KAZANDI!")
        print("="*60)
        print(f"Özet: {description}\n")

        print("--- OYUNCU ROLLERİ ÖZETİ ---")
        for p in self.players:
            status = "CANLI" if p.is_alive else "ÖLÜ"
            print(f"- {p.name:<18} | Rolü: {p.role['name']:<25} | Taraf: {p.role['team']:<8} | Durum: {status}")
        print("="*60)

# ==============================================================================
# OYUNU BAŞLATMA
# ==============================================================================
if __name__ == "__main__":
    game = DeathNoteGame()
    game.setup_game()
    game.start_night_phase()
