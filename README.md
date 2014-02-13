control_pc_via_lan_csharp
=========================

Local PC control over lan via C#
https://kishordgupta.wordpress.com/2011/02/03/controlling-pc-and-remote-access-via-lan-in-c


Controlling PC And Remote Access via lan in c#
Posted on February 3, 2011 by kishordgupta
Author
Mahamud Hasan
Wasif Islam
kishor datta gupta

we  develop a software which perform basic PC controlling operations and  complete remote access using C#. With our software we can establish a connection to any computer via the LAN in just a few seconds and remotely control this computer just as if you were sitting in front of it.

our software can able to do following tasks

We can connect server pc and client pc.
Maximum 5 clients can connect to the server.
Server and client can transfer data with each other.
Only server can tranfer file to the client.
Server pc can shutdown, restart and logoff to the client pc.
Using remote access server pc can see the desktop of the client.
Server pc can browse client pc and install any kind of software.
Server pc can access to the computer to be serviced and it can perform any action even if no-one is sitting in front of it.
Features:Simple implementation of a TCP client server relationship



When the server program is run, it will indicate at which IP it is running and the port it is listening to. Using Tcp listener server can listen its ip address and port. “Dns.GetHostByName(Dns.GetHostName()).AddressList[0];” –Using this code we get the server ip address. At the same time a thread will be running. This thread will waiting for client connection.

Now run the client program and write down the server ip address. Then press the “Connect” button and it establishes a connection with the server.



When a connection is established the server will display the client IP address from where it has accepted the connection and client will ask for the string which is to be transmitted to the server. The server on reciept of the string will display it, send an acknowledgement which will be recieved by the client.

The client can be either run from the same machine as the server or from a different machine. If run from a different machine then a network connection should exist between the machines running the server and client programs.



When any client connect with the server then from the server display a combobox named “Client IP List” contains all client IP.

When connection is established between server and client then server and client can transfer message with each other.



When server send message then client recieve this message. At the same time client can send message to the server from the Message textbox.Then server also recieve data from the client. Server can transfer file to the client. Using Networkstream server can transfer file. When we press File Transfer button then a file dialoug box is open. Then select a file and send it.

There are controll operations that the server will perform to the client. If server want to shut down the client pc then server can select the shut down button and activate it. Then client pc will shut down. Server can do three operations if it want. These are Shutdown , restart and log off.

We use Remote Desktop a great deal. Using remote access server can browse the client PC. All kind of operation can be performed by the server when remote is active,

For that we get a help from a codeproject article . Thanks to it we make a very effective remote access,



We will be using AxMSTSCLib an ActiveX component in our program to connect to the remote computer. It’s not that hard to build a remote desktop application in .NET. Microsoft has a “Microsoft RDP client control” ActiveX control that we will be using in our application.We will start by creating a Windows application in the Visual Studio IDE. Add a reference to “Microsoft Terminal Services Control Type Library” from the COM tab. This will add MSTSCLib.dll to the project.

To add MSTSC to the toolbox, right click the toolbox and select “Choose Items…”. Now add “Microsoft Terminal Services control from the COM tab.

Drag the newly added control from toolbox to the form.

Here is how we write the Connect button click event.

rdp.Server = txtServer.Text;
rdp.UserName = txtUserName.Text;
IMsTscNonScriptable secured = (IMsTscNonScriptable)rdp.GetOcx();
secured.ClearTextPassword = txtPassword.Text;
rdp.Connect();

Now assign the properties (Server, UserName) of RDP control with the textbox values. Here’s how easy it is to login to remote machine. However there is one catch, there is no direct method in RDP control through which you can pass the username and password to login to the remote desktop.  Due to security reasons, you have to implement an interface (IMsTscNonScriptable) to cast it separately.
IMsTscNonScriptable secured = IMsTscNonScriptable)rdp.GetOcx();
secured.ClearTextPassword = txtPassword.Text;



To disconnect from the remote desktop session, we just need to call the Disconnect() method.

Before disconnecting, we want to ensure that the connection is still available. We don’t want to disconnect if it is already disconnected.

if (rdp.Connected.ToString() == "1")
 rdp.Disconnect();
Though we have developed our software using the platform independent programming language C# but our software is not totally platform independent at all. Because our software only run in the .net framework version 3.5. But we are tried our best to do that. There are a few limitations in our software cause it can remotely connect to only one client pc at a time.
