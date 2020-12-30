//
// Created by henrik on 29.12.20
//

#include <algorithm>
#include <chrono>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <string>
#include <sstream>
#include <vector>


namespace fs = std::filesystem;

int main(int argc, char* argv[])
{
    const char* FILE_EXT{".dem"};
    const char* HEADER = "HL2DEMO";
    constexpr size_t STR_LEN{260},
                     SVR_NAME{16},
                     CL_NAME{276},
                     MAP_NAME{536},
                     DEMO_LEN{1056};


    fs::path demo_dir, target_dir;

    if(argc <= 1)
    {
        demo_dir = fs::current_path();
        target_dir = demo_dir;
    }
    else if(argc == 2)
    {
        demo_dir = argv[1];
        target_dir = demo_dir;
    }
    else
    {
        demo_dir = argv[1];
        target_dir = argv[2];
    }

    std::clog << "Demo directory: " << demo_dir << '\n';
    std::clog << "Target directory: " << target_dir << '\n';

    std::vector<std::uint8_t> buf(260);
    std::size_t num_moved_demos{};
    for(auto& entry : fs::directory_iterator(demo_dir))
    {
        std::fill_n(buf.begin(), buf.size(), 0);
        if(!(entry.is_regular_file() && entry.path().extension() == ".dem"))
            continue;

        std::ifstream demo_file(entry.path().string(), std::ios::binary);
        if(!demo_file.is_open())
        {
            std::clog << "Failed to open " << entry.path() << '\n';
            continue;
        }

        std::string header_str(7, '\0');
        demo_file.read(header_str.data(), header_str.size());
        if(header_str != HEADER)
        {
            std::clog << header_str << '\n';
            std::clog << entry.path().filename() << " is not a valid demo file\n";
            continue;
        }

        std::string server_name(260, '\0');
        demo_file.seekg(SVR_NAME);
        demo_file.read(server_name.data(), server_name.size());
        server_name.resize(std::strlen(server_name.c_str()));

        std::string client_name(260, '\0');
        demo_file.seekg(CL_NAME);
        demo_file.read(client_name.data(), client_name.size());
        client_name.resize(std::strlen(client_name.c_str()));

        std::string map_name(260, '\0');
        demo_file.seekg(MAP_NAME);
        demo_file.read(map_name.data(), map_name.size());
        map_name.resize(std::strlen(map_name.c_str()));

        float demo_len{};
        demo_file.seekg(DEMO_LEN);
        demo_file.read(reinterpret_cast<char*>(&demo_len), sizeof(demo_len));

        if(!demo_file.good())
        {
            std::clog << "Failed to read demo header: " << entry.path().filename() << '\n';
            continue;
        }

        demo_file.close();

        std::stringstream date;
        std::string timestamp_str(entry.path().filename().string());
        timestamp_str.resize(timestamp_str.size() - entry.path().extension().string().size());
        try
        {
            std::time_t timestamp{std::stol(timestamp_str)};
            date << std::put_time(std::localtime(&timestamp), "%Y_%m_%d_%Hh%Mm%Ss");
        }
        catch(const std::exception& e)
        {
            std::clog << timestamp_str << " is an invalid timestamp\n";
            date << "1970_01_01_0h0m0s";
        }

        unsigned hours{static_cast<unsigned>(demo_len) / 3600};
        unsigned minutes{(static_cast<unsigned>(demo_len) % 3600) / 60};
        unsigned seconds{(static_cast<unsigned>(demo_len) % 3600) % 60};

        std::string length{std::to_string(hours) + "h" + std::to_string(minutes) + "m" + std::to_string(seconds) + "s"};

        std::string filename;
        filename +=date.str();
        filename += "-";
        filename += map_name;
        filename += "-";
        filename += length;
        filename += "-";
        filename += client_name;
        filename += ".dem";

        try
        {
            fs::rename(entry.path(), target_dir / filename);
            std::ofstream dummy(entry.path().string(), std::ios::binary | std::ios::ate);
            if(!dummy.is_open())
            {
                std::clog << "Failed to create dummy file: " << entry.path() << '\n';
            }
        }
        catch(const fs::filesystem_error& e)
        {
            std::clog << "Failed to move file: " << e.what() << '\n';
            continue;
        }
        std::clog << entry.path() << "\t -> \t" << target_dir / filename << '\n';
        ++num_moved_demos;
    }

    std::clog << "Moved " << num_moved_demos << " demos\n";
}
